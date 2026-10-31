#!/usr/bin/env python3
"""Portable small-fixture validator. No full matches. Supply unchanged repository."""
import argparse,copy,hashlib,importlib.util,json,pathlib,subprocess,sys,time,unittest
HERE=pathlib.Path(__file__).resolve().parent

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',required=True,type=pathlib.Path)
    ap.add_argument('--output',type=pathlib.Path)
    args=ap.parse_args();repo=args.repo.resolve()
    sys.path.insert(0,str(repo/'game'));sys.path.insert(0,str(HERE))
    from aiwar.sdk import Environment,command_error
    frozen=json.loads((repo/'freeze/v0.2.0.json').read_text())['files']
    mismatches=[p for p,h in frozen.items() if hashlib.sha256((repo/p).read_bytes()).hexdigest()!=h]
    assert not mismatches,('frozen changes',mismatches)
    old=repo/'strategies/submissions/策略更新-GPTdot/independent-a-r3/agent.py'
    old_hash=hashlib.sha256(old.read_bytes()).hexdigest()
    assert old_hash=='818d5834ec12545cd632163a0dd5986ababf79fc893cbdb896d3cfe7c0f6e65e'
    a=load(HERE/'agent.py','new_policy');b=load(old,'baseline')
    opening={}
    for nation in (0,1):
        observation=Environment(seed=701220).observations()[nation]
        opening[nation]=a.Policy().decide(copy.deepcopy(observation))==b.Policy().decide(copy.deepcopy(observation))
    assert all(opening.values()),'Opening differs from exact baseline'
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
    tests=unittest.TextTestRunner(verbosity=2).run(suite)
    assert tests.wasSuccessful()
    env=Environment(seed=701220)
    observations=[env.observations()[0]]
    # One-hour state only checks cold protocol handling, not competitive strength.
    env.world.step(1);observations.append(env.world.observe(0))
    protocol=[]
    for index,o in enumerate(observations):
        request=dict(protocol_version=1,type='decide',request_id=f'fixture:{index}',observation=o,previous_outcomes=[])
        start=time.perf_counter()
        result=subprocess.run([sys.executable,str(HERE/'agent.py')],input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=2)
        elapsed=time.perf_counter()-start
        assert result.returncode==0 and not result.stderr,result.stderr
        reply=json.loads(result.stdout)
        assert reply['request_id']==request['request_id'] and reply['protocol_version']==1
        assert len(reply['commands'])<=100 and all(command_error(c) is None for c in reply['commands'])
        protocol.append(dict(hour=o['hour'],seconds=round(elapsed,6),request_id_correct=True,stderr=''))
    report=dict(source_sha256=hashlib.sha256((HERE/'agent.py').read_bytes()).hexdigest(),baseline_sha256=old_hash,
                frozen_count=len(frozen),frozen_mismatches=mismatches,opening_exact_match=opening,
                tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),protocol=protocol,
                scope='Small deterministic fixtures only; not evidence of win rate or comparative strength.')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.output:args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
