import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from aiwar.agents import PolicyPool
from aiwar.match import run_match
from aiwar.runner import run_one


class Pipe:
    def __init__(self,clock,delay,result):self.clock=clock;self.delay=delay;self.result=result
    def send(self,obs):self.clock[0]+=self.delay
    def recv(self):return self.result


def fake_pool(pipes):
    pool=PolicyPool.__new__(PolicyPool)
    pool.nations=tuple(range(len(pipes)));pool.styles=['march']*len(pipes);pool.timeout=2
    pool.pipes=dict(enumerate(pipes));pool.metrics=[dict(decisions=0,errors=0,timeouts=0,invalid_commands=0,malformed_commands=0) for _ in pipes]
    pool._start=Mock();pool._stop=Mock()
    return pool


def fake_world(n):
    world=Mock();world.nation_ids.return_value=tuple(range(n));world.cfg={'mode':'duel'}
    world.observe.side_effect=lambda n:{'nation':n}
    world.command.return_value={'ok':False,'error':'not owned'}
    return world


class AgentReporting(unittest.TestCase):
    def test_each_nation_receives_full_post_submission_budget(self):
        clock=[0.]
        pipes=[Pipe(clock,1,{'commands':[],'error':None,'completed_at':2.5}),
               Pipe(clock,1,{'commands':[],'error':None,'completed_at':3.5})]
        pool=fake_pool(pipes)
        def wait(pending,timeout):
            ready=min(pending,key=lambda p:p.result['completed_at'])
            if ready.result['completed_at']>clock[0]+timeout:
                clock[0]+=timeout;return []
            clock[0]=ready.result['completed_at'];return [ready]
        with patch('aiwar.agents.time.monotonic',side_effect=lambda:clock[0]),patch('aiwar.agents.wait',side_effect=wait):
            pool.cycle(fake_world(2))
        self.assertEqual([pool.last_timings[n]['deadline'] for n in range(2)],[3,4])
        self.assertEqual([m['timeouts'] for m in pool.metrics],[0,0])
        pool._stop.assert_not_called()

    def test_errors_timeouts_and_rejections_accumulate(self):
        clock=[0.]
        pipes=[Pipe(clock,0,{'commands':[{'type':'unknown'},{'type':'stop','unit':'foreign'}],'error':None,'completed_at':0}),
               Pipe(clock,0,{'commands':[],'error':'bad policy','completed_at':0}),
               Pipe(clock,0,{'commands':[],'error':None,'completed_at':9})]
        pool=fake_pool(pipes);world=fake_world(3)
        with patch('aiwar.agents.time.monotonic',return_value=0),patch('aiwar.agents.wait',side_effect=lambda p,timeout:p):
            pool.cycle(world);pool.cycle(world)
        self.assertEqual(pool.metrics[0]['invalid_commands'],4)
        self.assertEqual(pool.metrics[0]['malformed_commands'],2)
        self.assertEqual(pool.metrics[1]['errors'],2)
        self.assertEqual(pool.metrics[2]['timeouts'],2)
        self.assertEqual(pool.metrics[2]['errors'],2)
        self.assertEqual([m['decisions'] for m in pool.metrics],[2,2,2])

    def test_match_reports_rejected_commands(self):
        with tempfile.TemporaryDirectory() as tmp,patch('aiwar.match.JsonAgent.decide',return_value=([{'type':'unknown'}],None)):
            run_match([['placeholder'],['placeholder']],Path(tmp)/'run',days=.125)
            report=json.loads((Path(tmp)/'run/match.json').read_text())
            self.assertEqual(report['status'],'completed')
            self.assertEqual(report['invalid_commands'],[1,1])
            self.assertEqual(report['decisions'],[1,1])
            self.assertEqual(report['agent_timeouts'],[0,0])

    def test_formal_match_accepts_rotated_configuration(self):
        with tempfile.TemporaryDirectory() as tmp,patch('aiwar.match.JsonAgent.decide',return_value=([],None)):
            report=run_match([['placeholder'],['placeholder']],Path(tmp)/'run',days=.125,mode='realmap',
                             config={'culture_traits':False,'nations':['empire_s','khuzait'],'days':999,'mode':'duel'})
            self.assertFalse(report['config']['culture_traits'])
            self.assertEqual(report['config']['nations'],['empire_s','khuzait'])
            self.assertEqual(report['config']['days'],.125)
            self.assertEqual(report['config']['mode'],'realmap')

    def test_aborted_match_retains_failure_manifest(self):
        with tempfile.TemporaryDirectory() as tmp,patch('aiwar.match.JsonAgent.decide',return_value=([],'decision timeout; restarted')),patch('aiwar.match.Environment.step',side_effect=RuntimeError('tick failed')):
            with self.assertRaisesRegex(RuntimeError,'tick failed'):
                run_match([['placeholder'],['placeholder']],Path(tmp)/'run',days=.125)
            report=json.loads((Path(tmp)/'run/match.json').read_text())
            self.assertEqual(report['status'],'failed')
            self.assertEqual(report['failure']['type'],'RuntimeError')
            self.assertEqual(report['agent_errors'],[1,1])
            self.assertEqual(report['agent_timeouts'],[1,1])

    def test_runner_retains_failure_and_closes_pool(self):
        with patch('aiwar.runner.PolicyPool') as cls,patch('aiwar.runner.World.step',side_effect=RuntimeError('tick failed')):
            pool=cls.return_value;pool.metrics=[dict(errors=2,timeouts=1,invalid_commands=3) for _ in range(2)];pool.timeout=2
            report=run_one((1,.125,['manual','manual'],False,True,'duel'))
            self.assertEqual(report['status'],'failed')
            self.assertEqual(report['failure']['message'],'tick failed')
            self.assertEqual(report['agent_metrics'][1]['invalid_commands'],3)
            self.assertTrue(report['agent_metrics_available'])
            pool.close.assert_called_once()

if __name__=='__main__':unittest.main()
