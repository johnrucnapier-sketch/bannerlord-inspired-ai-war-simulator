import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aiwar.engine import World
from aiwar.policies import decide
from aiwar.patrols import decide as patrol
from aiwar.replay import replay

class CampaignP5Tests(unittest.TestCase):
    def test_war_commands_preserved_and_patrol_scoped(self):
        w=World(1,{'bandit_cap':0})
        observed_phases=set()
        for _ in range(168*4):
            for n in (0,1):
                obs=w.observe(n);snapshot=copy.deepcopy(obs)
                with patch('aiwar.policies.patrol_decide',return_value=[]) as call:
                    war=decide(obs,'march_p5')
                args=call.call_args.kwargs
                self.assertFalse(args['allow_create'])
                available=args['available_ids']
                default=decide(obs,'march')
                # The unchanged war planner is exactly the same command prefix.
                self.assertEqual(war,default[:len(war)])
                protected={c['unit'] for c in war if 'unit' in c}
                self.assertFalse(available & protected)
                full=decide(obs,'march_p5')
                self.assertEqual(full[:len(war)],war)
                for c in full[len(war):]:
                    self.assertIn(c['unit'],available)
                    self.assertNotIn(c['type'],('create','assemble','disband','siege','raid'))
                for c in full:
                    if c.get('campaign_phase'):observed_phases.add(c['campaign_phase'])
                    if c['type'] in ('assemble','siege'):observed_phases.add(c['type'])
                    result=w.command(n,c);self.assertTrue(result['ok'],(c,result))
                self.assertEqual(obs,snapshot)
            w.step(6)
        self.assertIn('rally',observed_phases)
        self.assertIn('assemble',observed_phases)
        w.check()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'save.json';w.save(path)
            self.assertEqual(replay(path).physics_digest(),w.physics_digest())

    def test_empty_patrol_pool_never_creates_or_commands(self):
        w=World(1)
        self.assertEqual(patrol(w.observe(0),'p5',available_ids=set(),allow_create=False),[])
