import asyncio
import tempfile
import subprocess
import sys
import json
import unittest
from pathlib import Path
from aiwar.engine import World
from aiwar.policies import decision_cycle,decide
from aiwar.replay import replay
from aiwar.server import Session
from aiwar.agents import PolicyPool

class Integration(unittest.TestCase):
    def test_cli_multiple_games_spawn(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'batch.json'
            subprocess.run([sys.executable,'-m','aiwar','--days','1','--games','2','--workers','2','--output',str(output)],check=True,stdout=subprocess.DEVNULL,timeout=20)
            report=json.loads(output.read_text())
            self.assertEqual(len(report['games']),2)
            self.assertTrue(all(g['result']['hour']==24 for g in report['games']))

    def test_control_loop_handles_stale_lost_city(self):
        w=World(1,{'bandit_cap':0})
        w.capture('c00',1,[6])
        # Force a historical ownership observation without stock fields.
        obs=w.observe(0)
        obs['cities'].append({'id':'old','nation':0,'x':14000,'y':14000,'stale':True})
        self.assertIsInstance(decide(obs),list)

    def test_map_mirrored(self):
        w=World()
        self.assertEqual(w.terrain,[list(reversed(row)) for row in reversed(w.terrain)])

    def test_award_clan_and_discard(self):
        w=World();w.capture('c10',0,[0],award_clan=4)
        self.assertEqual(w.cities['c10']['clan'],4)
        c=w.cities['c00']
        r=w.command(0,{'type':'dispatch','city':c['id'],'destination':'c01','food':100000})
        u=w.units[r['unit']]
        self.assertTrue(w.command(0,{'type':'discard','unit':u['id'],'food':50000})['ok'])
        self.assertEqual(u['cargo_food'],50000)

    def test_saved_journal_and_viewer_replay(self):
        w=World(1,{'bandit_cap':0})
        for _ in range(200):
            if w.hour%6==0:decision_cycle(w)
            w.step()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'state.json';w.save(p)
            self.assertEqual(replay(p).digest(),w.digest())
        s=Session();s.replaying=w;s.world=World(w.seed,w.cfg)
        while s.replaying is not None:s.advance()
        self.assertEqual(s.world.digest(),w.digest())
        self.assertTrue(s.paused)

    def test_isolated_policies_match_trusted_fast_path(self):
        a=World(1,{'bandit_cap':0});b=World(1,{'bandit_cap':0})
        pool=PolicyPool(timeout=5)
        try:
            for _ in range(12):
                decision_cycle(a);pool.cycle(b)
                a.step(6);b.step(6)
            self.assertEqual(a.digest(),b.digest())
        finally:pool.close()

if __name__=='__main__':unittest.main()
