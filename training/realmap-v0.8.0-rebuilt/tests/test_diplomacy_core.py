"""Core reconstruction tests, independently rerun against rebuilt source."""
import copy
import tempfile
from pathlib import Path
import unittest
from aiwar import diplomacy as d
from aiwar.engine import World
from aiwar.sdk import Environment, command_error
try:
    from .test_diplomacy_review import SmallWorld,relation,submit,treaty
except ImportError:
    from test_diplomacy_review import SmallWorld,relation,submit,treaty

class CoreTests(unittest.TestCase):
    def test_existing_enemy_bloc_sync(self):
        w=SmallWorld();relation(w,2,3,'alliance');relation(w,0,2,'war');relation(w,0,3,'war')
        treaty(w,0,1,'alliance');d.check(w)
        for x in (0,1):
            for y in (2,3):self.assertTrue(w.hostile(x,y))

    def test_nap_blocks_alliance_atomically(self):
        w=SmallWorld();relation(w,0,2,'war');relation(w,1,2,'nap');before=copy.deepcopy(w.relations)
        submit(w,0,'propose_alliance',target=1);r=d.resolve(w)
        self.assertEqual(r[0]['status'],'rejected');self.assertEqual(before,w.relations)

    def test_nap_expiration_and_war_block(self):
        w=SmallWorld();treaty(w,0,1,'nap');submit(w,1,'declare_war',target=0)
        self.assertEqual(d.resolve(w)[0]['status'],'rejected')
        w.hour+=w.cfg['diplomacy_nap_hours'];d.tick(w);self.assertEqual(w.relations['0']['1'],'peace')

    def test_whole_bloc_peace_and_nap_preservation(self):
        w=SmallWorld();relation(w,0,1,'alliance');relation(w,2,3,'alliance')
        for a in (0,1):
            for b in (2,3):relation(w,a,b,'war')
        treaty(w,0,2,'peace');d.check(w)
        for a in (0,1):
            for b in (2,3):self.assertEqual(w.relations[str(a)][str(b)],'peace')
        treaty(w,0,2,'nap');expiry=copy.deepcopy(d.state(w)['treaties']);treaty(w,0,2,'peace')
        self.assertEqual(expiry,d.state(w)['treaties'])

    def test_crossed_offers_do_not_deadlock(self):
        for kind in ('peace','nap','alliance'):
            w=SmallWorld()
            submit(w,0,'propose_'+kind,target=1);submit(w,1,'propose_'+kind,target=0);d.resolve(w)
            for n in (0,1):
                for p in d.observe(w,n)['incoming']:submit(w,n,'accept',proposal_id=p['id'])
            d.resolve(w);d.check(w);self.assertEqual(w.relations['0']['1'],kind)

    def test_conflict_order_independent(self):
        result=[]
        for reverse in (False,True):
            w=SmallWorld();submit(w,0,'propose_nap',target=1);d.resolve(w)
            pid=d.observe(w,1)['incoming'][0]['id']
            cmds=[('accept',{'proposal_id':pid}),('declare_war',{'target':0})]
            for action,args in cmds[::(-1 if reverse else 1)]:submit(w,1,action,**args)
            d.resolve(w);d.check(w);result.append(w.relations)
            self.assertEqual(w.relations['0']['1'],'peace')
        self.assertEqual(*result)

    def test_transitive_alliance_transactions_conflict(self):
        w=SmallWorld();submit(w,0,'propose_alliance',target=1);submit(w,2,'propose_alliance',target=1);d.resolve(w)
        for p in d.observe(w,1)['incoming']:submit(w,1,'accept',proposal_id=p['id'])
        d.resolve(w);d.check(w);self.assertEqual(w.relations['0']['1'],'peace')

    def test_uniform_alliance_expiration_leave_and_extinction(self):
        w=SmallWorld();treaty(w,0,1,'alliance');treaty(w,1,2,'alliance')
        expiries={t['expires_hour'] for t in d.state(w)['treaties'].values()};self.assertEqual(len(expiries),1)
        submit(w,0,'leave_alliance');d.resolve(w);d.check(w)
        self.assertEqual(w.relations['1']['2'],'alliance');self.assertEqual(w.relations['0']['1'],'peace')
        w.extinct_nations=[1];d.tick(w);self.assertFalse(d.state(w)['treaties'])

    def test_private_offers_reply_and_gate(self):
        w=SmallWorld();submit(w,0,'propose_peace',target=1);d.resolve(w)
        self.assertFalse(d.observe(w,2)['incoming']);self.assertFalse(d.observe(w,2)['events'])
        self.assertFalse(d.decision_due(w,0));self.assertTrue(d.observe(w,1)['reply_due'])
        pid=d.observe(w,1)['incoming'][0]['id'];submit(w,1,'reject',proposal_id=pid);d.resolve(w)
        self.assertFalse(d.observe(w,1)['reply_due'])
        w.cities['c']={'id':'c','nation':0};self.assertTrue(d.decision_due(w,0))
        submit(w,0,'hold');d.resolve(w);self.assertFalse(d.decision_due(w,0))

    def test_real_world_save_load_fog_determinism(self):
        w=World(31,dict(mode='realmap',diplomacy_enabled=True,bandit_cap=0));relation(w,0,1,'alliance')
        hidden=next(u for u in w.units.values() if u['nation']==1 and u['kind']=='party' and not w.visible(0,u))
        self.assertNotIn(hidden['id'],{u['id'] for u in w.observe(0)['units']})
        submit(w,0,'hold');submit(w,2,'propose_peace',target=3);d.resolve(w)
        before=w.observe(0);hidden['food']+=12345;self.assertEqual(before,w.observe(0))
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'world.json';w.save(p);restored=World.load(p)
            self.assertEqual(w.digest(),restored.digest());self.assertEqual(w.observe(3),restored.observe(3))
            pid=d.observe(w,3)['incoming'][0]['id']
            for world in (w,restored):submit(world,3,'accept',proposal_id=pid);world.step(1);world.check()
            self.assertEqual(w.digest(),restored.digest())

    def test_sdk_batch_and_schema(self):
        self.assertIsNone(command_error(dict(type='diplomacy',action='hold',reason={})))
        self.assertIsNotNone(command_error(dict(type='diplomacy',action='declare_war',target=True)))
        env=Environment(1,dict(diplomacy_enabled=True,decision_hours=1))
        out=env.step([[dict(type='diplomacy',action='propose_peace',target=1)],[]])
        pid=out['observations'][1]['diplomacy']['incoming'][0]['id']
        out=env.step([[],[dict(type='diplomacy',action='accept',proposal_id=pid)]])
        self.assertFalse(env.world.hostile(0,1));self.assertTrue(out['diplomatic_results']);env.world.check()

if __name__=='__main__':unittest.main()
