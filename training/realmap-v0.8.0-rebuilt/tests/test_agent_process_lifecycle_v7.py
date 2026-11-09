"""Host liveness tests, not a claim that policy processes are a security sandbox."""
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from aiwar.agents import PolicyPool, _PolicyConnection, _kill_process_tree
from aiwar.match import JsonAgent, run_match
from aiwar.sdk import PROTOCOL_VERSION


GOOD = """
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    print(json.dumps({'protocol_version': req.get('protocol_version'),
                      'request_id': req['request_id'], 'commands': []}), flush=True)
"""


def request(number=0, **extra):
    return {'protocol_version': PROTOCOL_VERSION, 'request_id': f'0:{number}', **extra}


def alive(pid):
    # Linux may retain an orphan zombie until the container's init reaps it.
    stat = Path(f'/proc/{pid}/stat')
    try:
        if stat.exists() and stat.read_text().split(') ', 1)[1].startswith('Z'):
            return False
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def eventually(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.01)
    return predicate()


class World:
    def __init__(self, nations=1, payload=''):
        self.nations = nations
        self.cfg = {'mode': 'duel'}
        self.payload = payload
        self.observed = []
        self.applied = []

    def nation_ids(self):
        return tuple(range(self.nations))

    def observe(self, n):
        self.observed.append(n)
        return {'nation': n, 'hour': 12, 'payload': self.payload}

    def command(self, n, command):
        assert len(self.observed) == self.nations
        self.applied.append(n)
        return {'ok': True}

    def emit(self, *args, **kwargs):
        pass


class AgentProcessLifecycleV7(unittest.TestCase):
    def agent(self, code, timeout=.15, stderr=subprocess.DEVNULL):
        agent = JsonAgent([sys.executable, '-c', code], stderr, timeout)
        self.addCleanup(agent.close)
        return agent

    def test_direct_timeout_and_close_are_bounded(self):
        agent = self.agent('import time; time.sleep(10)')
        started = time.monotonic()
        self.assertIn('decision timeout', agent.decide(request())[1])
        self.assertLess(time.monotonic() - started, .9)
        self.assertIsNone(agent.process)
        self.assertIsNone(agent._retired)
        agent.close()

    def test_wrapper_child_retaining_stdout_is_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'child.pid'
            code = f"""
import subprocess, sys, time
from pathlib import Path
p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2.5)'])
Path({str(pidfile)!r}).write_text(str(p.pid))
time.sleep(10)
"""
            agent = self.agent(code, timeout=.3)
            started = time.monotonic()
            self.assertIn('decision timeout', agent.decide(request())[1])
            self.assertLess(time.monotonic() - started, 1.2)
            self.assertTrue(pidfile.exists())
            pid = int(pidfile.read_text())
            if os.name == 'posix':
                self.assertTrue(eventually(lambda: not alive(pid)))
            self.assertIsNone(agent._retired)

    @unittest.skipUnless(os.name == 'posix', 'POSIX group survives its leader')
    def test_exited_wrapper_cannot_leave_ordinary_stdout_holder(self):
        code = "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2.5)'])"
        agent = self.agent(code, timeout=.2)
        started = time.monotonic()
        self.assertIn('decision timeout', agent.decide(request())[1])
        self.assertLess(time.monotonic() - started, .9)
        self.assertIsNone(agent._retired)

    def test_blocked_request_write_is_bounded(self):
        agent = self.agent('import time; time.sleep(10)')
        started = time.monotonic()
        self.assertIn('decision timeout', agent.decide(request(payload='x' * 2_000_000))[1])
        self.assertLess(time.monotonic() - started, 1)
        self.assertIsNone(agent._retired)

    def test_normal_json_eof_and_malformed_response_cleanup(self):
        agent = self.agent(GOOD, timeout=2)
        self.assertEqual(agent.decide(request()), ([], None))
        original = agent.process
        self.assertEqual(agent.decide(request(1)), ([], None))
        self.assertIs(agent.process, original)
        agent.close()
        self.assertIsNotNone(original.poll())
        for code in ('pass', "print('bad', flush=True)", "print('{}', flush=True)"):
            bad = self.agent(code, timeout=1)
            self.assertIsNotNone(bad.decide(request())[1])
            self.assertIsNone(bad.process)
            self.assertIsNone(bad._retired)

    def test_timeout_restarts_on_later_decision_without_thread_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'once'
            code = f"""
from pathlib import Path
import time
marker = Path({str(marker)!r})
if not marker.exists():
    marker.write_text('started')
    time.sleep(10)
""" + GOOD
            agent = self.agent(code, timeout=.3)
            self.assertIn('decision timeout', agent.decide(request())[1])
            self.assertEqual(agent.decide(request(1)), ([], None))
            agent.close()
            self.assertIsNone(agent._retired)
        before = {t.ident for t in threading.enumerate() if t.name.startswith('agent-')}
        agent = self.agent('import time; time.sleep(10)', timeout=.03)
        for n in range(8):
            self.assertIn('decision timeout', agent.decide(request(n))[1])
            self.assertIsNone(agent._retired)
        after = {t.ident for t in threading.enumerate() if t.name.startswith('agent-')}
        self.assertEqual(before, after)

    def test_stderr_pipe_is_drained_without_retaining_diagnostics(self):
        agent = self.agent("import sys; sys.stderr.write('x' * 2_000_000); sys.stderr.flush()\n" + GOOD,
                           timeout=2, stderr=subprocess.PIPE)
        self.assertEqual(agent.decide(request()), ([], None))
        agent.close()
        self.assertIsNone(agent._retired)

    @unittest.skipUnless(os.name == 'posix', 'POSIX escape/retained-pipe behavior')
    def test_escaped_pipe_holder_does_not_block_or_accumulate_generations(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'escaped.pid'
            code = f"""
import subprocess, sys, time
from pathlib import Path
p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
Path({str(pidfile)!r}).write_text(str(p.pid))
time.sleep(10)
"""
            agent = self.agent(code, timeout=.3, stderr=subprocess.PIPE)
            pid = None
            try:
                started = time.monotonic()
                self.assertIn('decision timeout', agent.decide(request())[1])
                self.assertLess(time.monotonic() - started, 1.1)
                pid = int(pidfile.read_text())
                retired = agent._retired
                self.assertIsNotNone(retired)
                threads = {t.ident for t in threading.enumerate() if t.name.startswith('agent-')}
                for n in range(20):
                    self.assertIn('cleanup pending', agent.decide(request(n))[1])
                    self.assertIs(agent._retired, retired)
                    agent.close()
                self.assertEqual(threads, {t.ident for t in threading.enumerate() if t.name.startswith('agent-')})
                os.kill(pid, signal.SIGKILL)
                pid = None
                self.assertTrue(eventually(retired.release_finished))
                agent.argv = [sys.executable, '-c', GOOD]
                self.assertEqual(agent.decide(request(99)), ([], None))
            finally:
                if pid is not None:
                    os.kill(pid, signal.SIGKILL)
                agent.close()

    def test_eight_agent_batch_timeout_does_not_consume_peer_budgets(self):
        agents = [self.agent('import time; time.sleep(10)', timeout=.6)]
        agents += [self.agent('import time; time.sleep(.12)\n' + GOOD, timeout=.6) for _ in range(7)]
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=8) as executor:
            replies = list(executor.map(lambda agent: agent.decide(request()), agents))
        self.assertLess(time.monotonic() - started, 1.6)
        self.assertIn('decision timeout', replies[0][1])
        self.assertEqual(replies[1:], [([], None)] * 7)

    def test_eight_nation_match_preserves_failure_and_decision_counts(self):
        good = [sys.executable, '-c', GOOD]
        bad = [sys.executable, '-c', 'import time; time.sleep(10)']
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'match'
            run_match([bad] + [good] * 7, out, days=.125, timeout=.6, mode='realmap')
            manifest = json.loads((out / 'match.json').read_text())
            self.assertEqual(manifest['status'], 'completed')
            self.assertEqual(manifest['decisions'], [1] * 8)
            self.assertEqual(manifest['agent_timeouts'], [1] + [0] * 7)
            self.assertEqual(manifest['agent_errors'], [1] + [0] * 7)
            requests = [json.loads((out / f'nation-{n}.jsonl').read_text().splitlines()[0])['request']
                        for n in range(8)]
            self.assertEqual([r['observation']['hour'] for r in requests], [0] * 8)

    def test_windows_tree_cleanup_is_bounded_and_handles_unavailable_taskkill(self):
        with patch('aiwar.agents.os.name', 'nt'), patch('aiwar.agents.subprocess.run') as run:
            _kill_process_tree(123, timeout=.07)
            self.assertEqual(run.call_args.args[0], ['taskkill', '/PID', '123', '/T', '/F'])
            self.assertEqual(run.call_args.kwargs['timeout'], .07)
            for error in (OSError('missing taskkill'), subprocess.TimeoutExpired('taskkill', .07)):
                run.side_effect = error
                _kill_process_tree(123, timeout=.07)

    @unittest.skipUnless(os.name == 'posix', 'POSIX session creation')
    def test_json_agent_owns_a_separate_process_group(self):
        agent = self.agent(GOOD, timeout=2)
        self.assertEqual(agent.decide(request()), ([], None))
        self.assertEqual(os.getpgid(agent.process.pid), agent.process.pid)
        self.assertNotEqual(os.getpgid(agent.process.pid), os.getpgrp())


class PolicyProcessLifecycleV7(unittest.TestCase):
    def modules(self, sources):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sys.path.insert(0, tmp.name)
        self.addCleanup(sys.path.remove, tmp.name)
        names = []
        for n, source in enumerate(sources):
            name = f'lifecycle_policy_{Path(tmp.name).name}_{n}'
            (Path(tmp.name) / f'{name}.py').write_text(source)
            names.append(name)
        return names, Path(tmp.name)

    def test_import_hang_large_observations_and_eight_independent_budgets(self):
        good = "def decide(obs, style):\n    return [{'type': 'stop', 'unit': str(obs['nation'])}]\n"
        names, tmp = self.modules([good, good])
        marker = tmp / 'first_import'
        (tmp / f'{names[0]}.py').write_text(f"""
from pathlib import Path
import time
marker = Path({str(marker)!r})
if not marker.exists():
    marker.write_text('started')
    time.sleep(10)
""" + good)
        pool = PolicyPool(modules=[names[0]] + [names[1]] * 7, styles=['march'] * 8, timeout=1)
        self.addCleanup(pool.close)
        world = World(8, payload='x' * 2_000_000)
        started = time.monotonic()
        pool.cycle(world)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual([m['timeouts'] for m in pool.metrics], [1] + [0] * 7)
        self.assertEqual([m['errors'] for m in pool.metrics], [1] + [0] * 7)
        self.assertEqual([m['decisions'] for m in pool.metrics], [1] * 8)
        self.assertEqual(world.applied, list(range(1, 8)))
        world.observed.clear()
        pool.cycle(world)
        self.assertEqual([m['timeouts'] for m in pool.metrics], [1] + [0] * 7)
        self.assertEqual([m['errors'] for m in pool.metrics], [1] + [0] * 7)
        self.assertEqual([m['decisions'] for m in pool.metrics], [2] * 8)
        pool.close()
        self.assertEqual(pool.processes, {})
        self.assertEqual(pool.pipes, {})

    def test_oversized_policy_reply_is_rejected_and_restarted(self):
        names, _ = self.modules(["def decide(obs, style):\n    return [{'type': 'stop', 'unit': 'x' * 2_000_000}]\n"])
        pool = PolicyPool(modules=names, styles=['march'], timeout=1)
        self.addCleanup(pool.close)
        original_pid = pool.processes[0].pid
        pool.cycle(World())
        self.assertEqual(pool.metrics[0]['errors'], 1)
        self.assertEqual(pool.metrics[0]['timeouts'], 0)
        self.assertNotEqual(original_pid, pool.processes[0].pid)

    @unittest.skipUnless(os.name == 'posix', 'POSIX raw pipe framing')
    def test_partial_response_frame_never_reaches_main_thread_recv(self):
        ctx = mp.get_context('spawn')
        parent, child = ctx.Pipe()
        wrapped = _PolicyConnection(parent, ctx)
        self.addCleanup(wrapped.close)
        try:
            wrapped.send({'large': 'x' * 10000})
            self.assertEqual(child.recv(), {'large': 'x' * 10000})
            os.write(child.fileno(), struct.pack('!i', 100) + b'partial')
            started = time.monotonic()
            self.assertEqual(mp.connection.wait([wrapped], timeout=.1), [])
            self.assertLess(time.monotonic() - started, .5)
        finally:
            wrapped.close()
            child.close()
            self.assertTrue(wrapped.join(1))

    @unittest.skipUnless(os.name == 'posix', 'POSIX escaped inherited policy pipe')
    def test_escaped_policy_pipe_defers_restart_without_new_threads(self):
        names, tmp = self.modules([''])
        pidfile = tmp / 'escaped.pid'
        (tmp / f'{names[0]}.py').write_text(f"""
import os, time
from pathlib import Path
def decide(obs, style):
    marker = Path({str(pidfile)!r})
    if marker.exists():
        return []
    pid = os.fork()
    if pid == 0:
        os.setsid()
        time.sleep(30)
        os._exit(0)
    marker.write_text(str(pid))
    time.sleep(10)
""")
        pool = PolicyPool(modules=names, styles=['march'], timeout=.5)
        self.addCleanup(pool.close)
        escaped_pid = None
        try:
            pool.cycle(World())
            escaped_pid = int(pidfile.read_text())
            retired_pid = pool.processes[0].pid
            retired_pipe = pool.pipes[0]
            self.assertEqual(pool.metrics[0]['timeouts'], 1)
            self.assertTrue(retired_pipe.thread.is_alive())
            started = time.monotonic()
            for _ in range(3):
                pool.cycle(World())
                self.assertEqual(pool.processes[0].pid, retired_pid)
                self.assertIs(pool.pipes[0], retired_pipe)
            self.assertLess(time.monotonic() - started, .5)
            self.assertEqual(pool.metrics[0]['timeouts'], 1)
            self.assertEqual(pool.metrics[0]['errors'], 4)
            os.kill(escaped_pid, signal.SIGKILL)
            escaped_pid = None
            self.assertTrue(eventually(lambda: not retired_pipe.thread.is_alive()))
            pool.cycle(World())  # Reports the skipped decision and relaunches.
            self.assertNotEqual(pool.processes[0].pid, retired_pid)
            pool.cycle(World())
            self.assertEqual(pool.metrics[0]['errors'], 5)
            self.assertEqual(pool.metrics[0]['timeouts'], 1)
        finally:
            if escaped_pid is not None:
                os.kill(escaped_pid, signal.SIGKILL)
            pool.close()

    @unittest.skipUnless(os.name == 'posix', 'POSIX policy process groups')
    def test_policy_timeout_kills_ordinary_subprocess_child(self):
        names, tmp = self.modules([''])
        pidfile = tmp / 'child.pid'
        (tmp / f'{names[0]}.py').write_text(f"""
import subprocess, sys, time
from pathlib import Path
def decide(obs, style):
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    Path({str(pidfile)!r}).write_text(str(p.pid))
    time.sleep(10)
""")
        pool = PolicyPool(modules=names, styles=['march'], timeout=.5)
        self.addCleanup(pool.close)
        pool.cycle(World())
        self.assertEqual(pool.metrics[0]['timeouts'], 1)
        self.assertTrue(pidfile.exists())
        self.assertTrue(eventually(lambda: not alive(int(pidfile.read_text()))))
        self.assertNotEqual(pool.processes[0].pid, os.getpid())


if __name__ == '__main__':
    unittest.main()
