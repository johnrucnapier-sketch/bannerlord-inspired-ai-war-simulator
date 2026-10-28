"""Agent SDK v1. The World remains the sole owner of game rules."""
import copy
import hashlib
import json
from pathlib import Path
from .engine import World

PROTOCOL_VERSION = 1
MAX_COMMANDS = 100
COMMAND_FIELDS = {
    'move': {'unit': str, 'x': int, 'y': int},
    'stop': {'unit': str}, 'attack': {'unit': str, 'target': str},
    'siege': {'unit': str, 'target': str}, 'raid': {'unit': str, 'target': str},
    'create': {'city': str, 'count': int}, 'recruit': {'city': str, 'count': int},
    'transfer': {'unit': str, 'target': str, 'count': int},
    'assemble': {'unit': str, 'units': list}, 'disband': {'unit': str},
    'dispatch': {'city': str, 'destination': str}, 'supply': {'unit': str, 'target': str},
    'discard': {'unit': str, 'food': int}, 'set_strength': {'unit': str, 'target': int},
}
OPTIONAL_FIELDS = {'clan': int, 'source': str, 'unit': str, 'food': int,
                   'wounded': bool, 'award_clan': int, 'campaign_target': str,
                   'relief_action': str, 'relief_city': str}


def command_error(cmd):
    if not isinstance(cmd, dict) or not isinstance(cmd.get('type'), str):
        return 'command must be an object with a string type'
    fields = COMMAND_FIELDS.get(cmd['type'])
    if fields is None:
        return 'unknown command type'
    for key, kind in fields.items():
        if type(cmd.get(key)) is not kind:
            return f'{key} must be {kind.__name__}'
    for key, kind in OPTIONAL_FIELDS.items():
        if key in cmd and key not in fields and type(cmd[key]) is not kind:
            return f'{key} must be {kind.__name__}'
    if 'units' in cmd and (type(cmd['units']) is not list or any(type(i) is not str for i in cmd['units'])):
        return 'units must be a list of IDs'
    return None


class Environment:
    """Trusted in-process host API; give agents observations, never this object."""
    def __init__(self, seed=1, config=None):
        self.config = copy.deepcopy(config or {})
        self.reset(seed)

    def reset(self, seed=1):
        self.world = World(seed, self.config)
        self.last_transition = None
        return self.observations()

    def observations(self):
        return [self.world.observe(n) for n in (0, 1)]

    def step(self, actions):
        if self.world.result:
            raise ValueError('episode already finished; reset first')
        if not isinstance(actions, (list, tuple)) or len(actions) != 2:
            raise ValueError('actions must contain two command lists')
        if self.world.cfg.get('mode') == 'rural' and actions[1]:
            raise ValueError('single-nation mode requires an empty second action list')
        # Validate both envelopes before making any changes.
        if any(type(a) is not list or len(a) > MAX_COMMANDS for a in actions):
            raise ValueError('each side requires a list of at most 100 commands')
        actions = json.loads(json.dumps(actions, allow_nan=False))
        before = self.observations()
        hour = self.world.hour
        outcomes = [[], []]
        for n in (0, 1):
            for cmd in actions[n]:
                error = command_error(cmd)
                outcomes[n].append({'ok': False, 'error': error} if error else self.world.command(n, cmd))
        self.world.step(self.world.cfg['decision_hours'])
        self.last_transition = {'hour': hour, 'observations': before,
                                'actions': actions, 'outcomes': outcomes}
        done = self.world.result is not None
        # Only terminal win/loss; no strategy-specific reward shaping.
        winner = self.world.result['winner'] if done else None
        rewards = [0, 0] if winner is None else [1 if n == winner else -1 for n in (0, 1)]
        if done and self.world.cfg.get('mode') == 'rural':
            rewards = [self.world.result['score']['population_gain'], 0]
        return {'observations': self.observations(), 'outcomes': outcomes,
                'rewards': rewards, 'terminated': done,
                'result': copy.deepcopy(self.world.result)}

    def export(self, directory):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        w = self.world
        w.save(path / 'final.save.json')
        report = {'protocol_version': PROTOCOL_VERSION, 'rule_version': w.cfg['version'],
                  'seed': w.seed, 'hour': w.hour, 'result': w.result, 'config': w.cfg,
                  'config_sha256': hashlib.sha256(json.dumps(w.cfg, sort_keys=True).encode()).hexdigest(),
                  'physics_digest': w.physics_digest(), 'stats': w.stats,
                  'totals': w.observer_totals(), 'captures': w.history}
        (path / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
