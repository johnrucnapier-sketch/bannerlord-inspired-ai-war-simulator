"""Cross-language JSONL agent match host: python -m aiwar.match --help."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from .agents import PROCESS_CLEANUP_TIMEOUT, _kill_process_tree
from .sdk import Environment, PROTOCOL_VERSION, MAX_COMMANDS

MAX_RESPONSE_BYTES = 1_048_576


class _JsonProcess:
    """Own the streams until their I/O threads finish, even after a timeout.

    Buffered stream.close() may wait forever for another thread's I/O lock.
    Never call it on a live reader/writer from the match thread. An escaped
    descendant can retain a pipe after process-group/tree cleanup; retain only
    this one retired generation and defer relaunch until its I/O exits. This
    bounds host cleanup time and per-agent threads, not hostile process access.
    """
    def __init__(self, process):
        self.process = process
        self.retired = threading.Event()
        self.exchange_thread = None
        self.stderr_thread = None
        if process.stderr is not None:
            # File-backed stderr (the normal match path) needs no drainer.
            # PIPE is accepted too; discard diagnostics rather than allowing
            # an undrained pipe or an unbounded in-memory log to block a policy.
            self.stderr_thread = threading.Thread(target=self._drain_stderr,
                                                  name='agent-stderr', daemon=True)
            self.stderr_thread.start()

    def _drain_stderr(self):
        try:
            while self.process.stderr.read(65536):
                pass
        except (OSError, ValueError):
            pass
        finally:
            self.process.stderr.close()

    def close_exchange_streams(self):
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                try:
                    # Discard a failed writer's buffered tail instead of
                    # flushing it into a pipe retained by a descendant.
                    if hasattr(stream, 'raw'):
                        stream.raw.close()
                    stream.close()
                except (OSError, ValueError):
                    pass

    def release_finished(self):
        exchange_done = self.exchange_thread is None or not self.exchange_thread.is_alive()
        stderr_done = self.stderr_thread is None or not self.stderr_thread.is_alive()
        if exchange_done:
            self.close_exchange_streams()
        return exchange_done and stderr_done and self.process.poll() is not None

    def stop(self):
        deadline = time.monotonic() + PROCESS_CLEANUP_TIMEOUT
        self.retired.set()
        _kill_process_tree(self.process.pid)
        if self.process.poll() is None:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
        try:
            self.process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        for thread in (self.exchange_thread, self.stderr_thread):
            if thread is not None:
                thread.join(timeout=max(0, deadline - time.monotonic()))
        return self.release_finished()


class JsonAgent:
    def __init__(self, argv, stderr, timeout=2):
        if not isinstance(argv, list) or not argv or any(type(s) is not str for s in argv):
            raise ValueError('agent command must be a nonempty JSON array of strings')
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        self.argv, self.timeout, self.stderr = argv, timeout, stderr
        self.process = None
        self._running = None
        self._retired = None

    def close(self):
        running = self._running
        self.process = self._running = None
        if running is not None:
            if not running.stop():
                self._retired = running
        if self._retired is not None and self._retired.release_finished():
            self._retired = None

    def decide(self, request):
        if self._retired is not None:
            if not self._retired.release_finished():
                return [], 'previous process cleanup pending; restart deferred'
            self._retired = None
        try:
            if self.process is None:
                self.process = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=self.stderr, shell=False,
                                                start_new_session=(os.name == 'posix'))
                self._running = _JsonProcess(self.process)
        except OSError as e:
            return [], f'launch: {e}'
        p, running = self.process, self._running
        result = []
        def exchange():
            try:
                p.stdin.write((json.dumps(request, ensure_ascii=False) + '\n').encode('utf-8'))
                p.stdin.flush()
                line = p.stdout.readline(MAX_RESPONSE_BYTES + 1)
                if len(line) > MAX_RESPONSE_BYTES or not line.endswith(b'\n'):
                    raise ValueError('missing or oversized response line')
                data = json.loads(line)
                if type(data) is not dict or data.get('protocol_version') != PROTOCOL_VERSION or data.get('request_id') != request['request_id']:
                    raise ValueError('protocol_version/request_id mismatch')
                commands = data.get('commands')
                if type(commands) is not list or len(commands) > MAX_COMMANDS:
                    raise ValueError('commands must be a list of at most 100 commands')
                json.dumps(commands, allow_nan=False)
                result.append((commands, None))
            except Exception as e:
                result.append(([], f'{type(e).__name__}: {e}'))
            finally:
                if running.retired.is_set():
                    running.close_exchange_streams()
        thread = running.exchange_thread = threading.Thread(target=exchange, name='agent-exchange', daemon=True)
        thread.start(); thread.join(self.timeout)
        if thread.is_alive():
            self.close()
            return [], 'decision timeout; process restarted next decision when cleanup completes'
        commands, error = result[0]
        if error:
            self.close()
        return commands, error


def run_match(commands, output, seed=1, days=None, timeout=2, mode="duel", config=None):
    if days is None:days=840 if mode in ('realmap','rural') else 1680
    if days <= 0 or timeout <= 0:
        raise ValueError('days and timeout must be positive')
    if mode not in ('duel','rural','realmap'):raise ValueError('unknown mode')
    env = Environment(seed, {**(config or {}), 'days': days, 'mode': mode})
    nations = (0,) if mode == 'rural' else env.world.nation_ids()
    if len(commands) != len(nations):raise ValueError(f'expected {len(nations)} agents for {mode}')
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)  # Never overwrite a previous dataset.
    logs, errors, agents = [], [], []
    failures = [0 for _ in env.world.nation_ids()]
    timeouts = [0 for _ in env.world.nation_ids()]
    invalid = [0 for _ in env.world.nation_ids()]
    decisions = [0 for _ in env.world.nation_ids()]
    manifest = {'protocol_version': PROTOCOL_VERSION, 'agents': commands,
                'timeout_seconds': timeout, 'agent_errors': failures,
                'agent_timeouts': timeouts, 'invalid_commands': invalid, 'decisions': decisions,
                'command_order': list(nations), 'mode': mode, 'status': 'running',
                'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(Path(__file__).parent.glob('*.py'))}}
    def write_manifest():
        manifest['hour']=env.world.hour
        (path / 'match.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    write_manifest()
    try:
        for n in nations:
            logs.append((path / f'nation-{n}.jsonl').open('w', encoding='utf-8'))
            errors.append((path / f'agent-{n}.stderr.log').open('wb'))
            agents.append(JsonAgent(commands[n], errors[n], timeout))
        previous = [[] for _ in env.world.nation_ids()]
        with ThreadPoolExecutor(max_workers=len(nations)) as executor:
            while not env.world.result:
                observations = env.observations()
                requests = [{'protocol_version': PROTOCOL_VERSION, 'type': 'decide',
                             'request_id': f'{n}:{env.world.hour}', 'observation': observations[n],
                             'previous_outcomes': previous[n]} for n in nations]
                futures = [executor.submit(agents[n].decide, requests[n]) for n in nations]
                replies = [f.result() for f in futures]
                for n in nations:
                    decisions[n]+=1
                    failures[n]+=replies[n][1] is not None
                    timeouts[n]+=bool(replies[n][1] and replies[n][1].startswith('decision timeout'))
                step = env.step([r[0] for r in replies] + ([[]] if mode == 'rural' else []))
                previous = step['outcomes']
                for n in nations:
                    invalid[n] += sum(not r.get('ok',False) for r in previous[n])
                    logs[n].write(json.dumps({'request': requests[n], 'commands': replies[n][0],
                        'agent_error': replies[n][1], 'outcomes': previous[n]}, ensure_ascii=False) + '\n')
                    logs[n].flush()
                env.world.check()
        for n in nations:
            logs[n].write(json.dumps({'type': 'terminal', 'observation': step['observations'][n],
                                     'reward': step['rewards'][n]}, ensure_ascii=False) + '\n')
        report = env.export(path)
        manifest.update(status='completed',failure=None)
        write_manifest()
        return report
    except BaseException as exc:
        manifest.update(status='failed',failure={'type':type(exc).__name__,'message':str(exc),'hour':env.world.hour})
        write_manifest()
        raise
    finally:
        for agent in agents: agent.close()
        for file in logs + errors: file.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['duel','rural','realmap'], default='duel')
    p.add_argument('--agent0', help='JSON argv array; no shell interpretation')
    p.add_argument('--config', default='{}', help='JSON world configuration overrides')
    p.add_argument('--nations', nargs='+', help='ordered kingdom IDs for realmap')
    p.add_argument('--agents', help='JSON list of argv arrays, one per nation')
    p.add_argument('--agent1', help='JSON argv array; no shell interpretation')
    p.add_argument('--output', required=True, help='new directory for match data')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--days', type=int, default=None, help='默认：公平1v1为1680天，真实地图为840天')
    p.add_argument('--timeout', type=float, default=2)
    a = p.parse_args()
    if a.agents:
        if a.agent0 or a.agent1:p.error('--agents cannot be combined with --agent0/--agent1')
        commands=json.loads(a.agents)
    else:
        if not a.agent0:p.error('provide --agents or --agent0')
        if a.mode != 'rural' and not a.agent1:p.error('provide --agents for all nations, or --agent0 and --agent1 for duel')
        if a.mode == 'rural' and a.agent1:p.error('single-nation mode only accepts --agent0')
        commands = [json.loads(a.agent0)] + ([json.loads(a.agent1)] if a.agent1 else [])
    if type(commands) is not list:p.error('--agents must be a JSON list')
    config=json.loads(a.config)
    if type(config) is not dict:p.error('--config must be a JSON object')
    if a.nations:config['nations']=a.nations
    report = run_match(commands, a.output, a.seed, a.days, a.timeout, a.mode, config)
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__': main()
