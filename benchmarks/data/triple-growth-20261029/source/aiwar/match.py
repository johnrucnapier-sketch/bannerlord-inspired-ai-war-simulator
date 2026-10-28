"""Cross-language JSONL agent match host: python -m aiwar.match --help."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import threading
from .sdk import Environment, PROTOCOL_VERSION, MAX_COMMANDS

MAX_RESPONSE_BYTES = 1_048_576


class JsonAgent:
    def __init__(self, argv, stderr, timeout=2):
        if not isinstance(argv, list) or not argv or any(type(s) is not str for s in argv):
            raise ValueError('agent command must be a nonempty JSON array of strings')
        self.argv, self.timeout, self.stderr = argv, timeout, stderr
        self.process = None

    def close(self):
        p = self.process
        if p:
            if p.poll() is None:
                p.kill()
            p.wait()
            p.stdin.close(); p.stdout.close()
            self.process = None

    def decide(self, request):
        try:
            if self.process is None:
                self.process = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=self.stderr, shell=False)
        except OSError as e:
            return [], f'launch: {e}'
        p = self.process
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
        thread = threading.Thread(target=exchange, daemon=True)
        thread.start(); thread.join(self.timeout)
        if thread.is_alive():
            p.kill(); p.wait(); thread.join(1)
            self.close()
            return [], 'decision timeout; process restarted next decision'
        commands, error = result[0]
        if error:
            self.close()
        return commands, error


def run_match(commands, output, seed=1, days=1680, timeout=2, mode="duel"):
    if days <= 0 or timeout <= 0:
        raise ValueError('days and timeout must be positive')
    if mode not in ('duel','rural'):raise ValueError('unknown mode')
    nations = (0,) if mode == 'rural' else (0,1)
    if len(commands) != len(nations):raise ValueError('wrong number of agents for mode')
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)  # Never overwrite a previous dataset.
    env = Environment(seed, {'days': days, 'mode': mode})
    logs, errors, agents = [], [], []
    failures = [0, 0]
    try:
        for n in nations:
            logs.append((path / f'nation-{n}.jsonl').open('w', encoding='utf-8'))
            errors.append((path / f'agent-{n}.stderr.log').open('wb'))
            agents.append(JsonAgent(commands[n], errors[n], timeout))
        previous = [[], []]
        with ThreadPoolExecutor(max_workers=2) as executor:
            while not env.world.result:
                observations = env.observations()
                requests = [{'protocol_version': PROTOCOL_VERSION, 'type': 'decide',
                             'request_id': f'{n}:{env.world.hour}', 'observation': observations[n],
                             'previous_outcomes': previous[n]} for n in nations]
                futures = [executor.submit(agents[n].decide, requests[n]) for n in nations]
                replies = [f.result() for f in futures]
                step = env.step([r[0] for r in replies] + ([[]] if mode == 'rural' else []))
                previous = step['outcomes']
                for n in nations:
                    failures[n] += replies[n][1] is not None
                    logs[n].write(json.dumps({'request': requests[n], 'commands': replies[n][0],
                        'agent_error': replies[n][1], 'outcomes': previous[n]}, ensure_ascii=False) + '\n')
                    logs[n].flush()
                env.world.check()
        for n in nations:
            logs[n].write(json.dumps({'type': 'terminal', 'observation': step['observations'][n],
                                     'reward': step['rewards'][n]}, ensure_ascii=False) + '\n')
        report = env.export(path)
        manifest = {'protocol_version': PROTOCOL_VERSION, 'agents': commands,
                    'timeout_seconds': timeout, 'agent_errors': failures,
                    'command_order': list(nations), 'mode': mode, 'status': 'completed',
                    'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(Path(__file__).parent.glob('*.py'))}}
        (path / 'match.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    finally:
        for agent in agents: agent.close()
        for file in logs + errors: file.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['duel','rural'], default='duel')
    p.add_argument('--agent0', required=True, help='JSON argv array; no shell interpretation')
    p.add_argument('--agent1', help='JSON argv array; no shell interpretation')
    p.add_argument('--output', required=True, help='new directory for match data')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--days', type=int, default=1680)
    p.add_argument('--timeout', type=float, default=2)
    a = p.parse_args()
    if a.mode == 'duel' and not a.agent1:p.error('1v1 requires --agent1')
    if a.mode == 'rural' and a.agent1:p.error('single-nation mode only accepts --agent0')
    commands = [json.loads(a.agent0)] + ([json.loads(a.agent1)] if a.agent1 else [])
    report = run_match(commands, a.output, a.seed, a.days, a.timeout, a.mode)
    print(json.dumps(report, ensure_ascii=False))

if __name__ == '__main__': main()
