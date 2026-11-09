"""New reconstructed diplomacy wrapper over byte-identical recovered Dev20."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
try:
    from aiwar import diplomacy_policy
except ModuleNotFoundError as error:
    if error.name != 'aiwar':
        raise
    sys.path.insert(0,str(ROOT/'training'/'realmap-v0.8.0-rebuilt'))
    from aiwar import diplomacy_policy
BASE = Path(__file__).resolve().parent/'military_baseline'
VERSION = 'dev20-diplomacy-v080-rebuilt-experimental'


def _load_baseline():
    path = list(sys.path); previous = sys.modules.get('dev19_base')
    try:
        def load(name,filename):
            spec = importlib.util.spec_from_file_location(name,BASE/filename)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            return module
        sys.modules['dev19_base'] = load('_rebuilt_dev19_base','dev19_base.py')
        return load('_rebuilt_dev20_baseline','agent.py')
    finally:
        sys.path[:] = path
        if previous is None:
            sys.modules.pop('dev19_base',None)
        else:
            sys.modules['dev19_base'] = previous


_baseline = _load_baseline()


def military_observation(obs):
    view = copy.deepcopy(obs); n = obs['nation']
    def hostile(nation):
        return diplomacy_policy.relation(obs,n,nation) == 'war'
    view['units'] = [u for u in view['units'] if u['nation'] == n or hostile(u['nation'])]
    view['villages'] = [v for v in view['villages'] if v['nation'] == n or hostile(v['nation'])]
    owners = {c['id']:c['nation'] for c in view['cities']}
    view['frontier_targets'] = [cid for cid in view.get('frontier_targets',[]) if cid in owners and hostile(owners[cid])]
    # Keep public/remembered geometry, never relabel an ally as an owned asset.
    return view


def audit_commands(obs,commands):
    owners = {x['id']:x['nation'] for key in ('units','cities','villages') for x in obs.get(key,[])}
    def allowed(target):
        return target in owners and diplomacy_policy.relation(obs,obs['nation'],owners[target]) == 'war'
    result = []
    safe_commands = []
    for group in military_groups(commands):
        invalid_transaction = (group[0]['type'] in ('disband','assemble') and any(
            c[k] in owners and not allowed(c[k]) for c in group
            for k in ('west_target','vanilla_target','campaign_target') if k in c))
        if not invalid_transaction:
            safe_commands.extend(group)
    for source in safe_commands:
        c = dict(source)
        if c['type'] in ('attack','siege','raid') and not allowed(c.get('target')):
            continue
        invalid = any(c[k] in owners and not allowed(c[k]) for k in ('west_target','vanilla_target','campaign_target') if k in c)
        if invalid:
            if c['type'] == 'assemble':
                continue
            for k in ('west_target','vanilla_target','campaign_target'):
                c.pop(k,None)
            if (c.get('west_task') in ('clan_campaign','rally','approach','scout','intercept','harass','raid_supply')
                    or c.get('vanilla_task') in ('approach','scout','siege','raid_supply')):
                c = dict(type='stop',unit=c['unit'])
        result.append(c)
    return result


class WesternPlanner(_baseline.WesternPlanner):
    def __init__(self,obs):
        self.original_observation = obs
        super().__init__(military_observation(obs))

    def run(self):
        return audit_commands(self.original_observation,super().run())


def military_groups(commands):
    i = 0
    while i < len(commands):
        group = [commands[i]]; i += 1
        if group[0]['type'] in ('disband','assemble'):
            while i < len(commands) and commands[i].get('unit') == group[0].get('unit') and commands[i]['type'] in ('assemble','move'):
                group.append(commands[i]); i += 1
        yield group


def bounded_military(commands,cap):
    """Preserve original-order prefix and whole formation transactions."""
    result = []
    for group in military_groups(commands):
        if len(result)+len(group) > cap:
            break
        result.extend(group)
    return result


def decide(observation,previous_outcomes=None):
    if observation.get('mode') != 'realmap' or not observation.get('logistics_limits',{}).get('rations_separate'):
        return []
    if not observation.get('diplomacy',{}).get('enabled'):
        return _baseline.decide(observation,previous_outcomes)
    diplomatic = diplomacy_policy.decide(observation)[:100]
    military = WesternPlanner(observation).run()
    return diplomatic+bounded_military(military,100-len(diplomatic))


def main():
    for line in sys.stdin:
        request = json.loads(line)
        print(json.dumps(dict(protocol_version=1,request_id=request['request_id'],
                              commands=decide(request['observation'],request.get('previous_outcomes')))),flush=True)


if __name__ == '__main__':
    main()
