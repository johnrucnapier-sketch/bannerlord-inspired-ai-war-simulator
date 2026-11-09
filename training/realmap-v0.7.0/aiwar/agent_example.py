"""Protocol example only: no strategic behavior. Replace decide to supply an agent."""
import json
import sys


def decide(observation, previous_outcomes):
    return []


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    for line in sys.stdin:
        request = json.loads(line)
        commands = decide(request['observation'], request['previous_outcomes'])
        print(json.dumps({'protocol_version': 1, 'request_id': request['request_id'],
                          'commands': commands}), flush=True)

if __name__ == '__main__': main()
