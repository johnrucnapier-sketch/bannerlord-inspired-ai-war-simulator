import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aiwar.sdk import Environment
from aiwar.policies import decision_cycle, default_styles
from aiwar.server import Session
from aiwar.match import run_match
from aiwar.viewer_strategies import ViewerStrategies


class MultinationalInterfaces(unittest.TestCase):
    def test_sdk_dynamic_and_atomic(self):
        env=Environment(1,{'mode':'realmap','days':1})
        self.assertEqual(len(env.observations()),8)
        before=env.world.physics_digest()
        with self.assertRaises(ValueError):env.step([[],[]])
        self.assertEqual(before,env.world.physics_digest())
        result=env.step([[] for _ in range(8)])
        self.assertEqual(len(result['outcomes']),8)
        self.assertEqual(len(result['rewards']),8)
        self.assertEqual([o['nation'] for o in result['observations']],list(range(8)))

    def test_snapshot_before_any_commands(self):
        world=Environment(1,{'mode':'realmap'}).world
        seen=[]
        def decide(obs,style):
            seen.append(obs['nation'])
            return [{'type':'unused'}]
        def command(n,cmd):
            self.assertEqual(seen,list(range(8)))
            return {'ok':True}
        with patch('aiwar.policies.decide',decide),patch.object(world,'command',command):
            self.assertEqual(len(decision_cycle(world)),8)
        self.assertEqual(default_styles('realmap'),('vanilla_v1',)*8)

    def test_server_private_views(self):
        session=Session(1)
        for n in session.world.nation_ids():
            obs=session.snapshot(n)
            self.assertEqual(obs['nation'],n)
            self.assertNotIn('observer_totals',obs)
            self.assertNotIn('observer_events',obs)
        obs=session.snapshot(None)
        self.assertEqual(len(obs['observer_totals']),8)
        self.assertIn('observer_events',obs)
        session.set_style(7,'manual')
        self.assertEqual(session.styles[7],'manual')

    def test_separate_builtin_processes(self):
        world=Environment(1,{'mode':'realmap'}).world
        runtime=ViewerStrategies()
        try:
            runtime.cycle(world,['vanilla_v1']*8,'interface-test')
            self.assertEqual(len({a.process.pid for a in runtime.agents.values()}),8)
            self.assertEqual(set(runtime.previous),set(range(8)))
        finally:runtime.close()

    def test_eight_agent_match(self):
        argv=[sys.executable,'-m','aiwar.baseline_agent','--style','manual']
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'match'
            report=run_match([argv]*8,out,days=0.125,mode='realmap',timeout=5)
            manifest=json.loads((out/'match.json').read_text())
            self.assertEqual(manifest['agent_errors'],[0]*8)
            self.assertEqual(manifest['command_order'],list(range(8)))
            for n in range(8):
                rows=[json.loads(s) for s in (out/f'nation-{n}.jsonl').read_text().splitlines()]
                self.assertEqual(rows[0]['request']['observation']['nation'],n)
                self.assertEqual(rows[-1]['type'],'terminal')

if __name__=='__main__':unittest.main()
