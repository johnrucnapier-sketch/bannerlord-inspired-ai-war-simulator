import unittest
from tests.legacy_world import LegacyWorld as World
from aiwar.policies import decide

class Campaigns(unittest.TestCase):
    def apply(self,w,n,commands):
        for cmd in commands:
            result=w.command(n,cmd)
            self.assertTrue(result['ok'],(cmd,result))

    def test_create_from_garrison_and_split_preserve_military_and_cap(self):
        w=World(1);c=w.cities['c00'];g=w.units[c['garrison']]
        u=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        before=w.observer_totals()[0]['military']
        r=w.command(0,dict(type='create',city=c['id'],count=30,source='garrison'))
        self.assertTrue(r['ok']);self.assertEqual(g['healthy'],20)
        self.assertEqual(w.observer_totals()[0]['military'],before)
        self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=30,source='garrison'))['ok'])
        r=w.command(0,dict(type='create',city=c['id'],count=10,source=u['id']))
        self.assertTrue(r['ok']);self.assertEqual(u['healthy'],20)
        self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=1,source='garrison'))['ok'])
        self.assertEqual(w.observer_totals()[0]['military'],before);w.check()

    def test_expansion_reserve_prevents_refill_consuming_new_party_fund(self):
        w=World(1);c=w.cities['c00'];c['recruits']=30
        w.arrivals();self.assertEqual(c['recruits'],30)
        cmds=decide(w.observe(0));created=[c for c in cmds if c['type']=='create' and c['city']=='c00']
        self.assertEqual(created[0]['source'],'recruits')
        self.apply(w,0,cmds)
        self.assertEqual(sum(u['kind']=='party' and u['clan']==0 for u in w.units.values()),2)

    def test_patrol_refill_target_and_unavailable_donor(self):
        w=World(1,{'expansion_reserve':0});c=w.cities['c00'];c['recruits']=100
        u=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        self.apply(w,0,[dict(type='set_strength',unit=u['id'],target=40)])
        w.arrivals();self.assertEqual(u['healthy'],40);self.assertEqual(c['recruits'],90)
        u['x']+=2000
        self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=10,source=u['id']))['ok'])
        w.units[c['garrison']]['wounded']=20;w.units[c['garrison']]['healthy']=0
        self.assertFalse(w.command(0,dict(type='create',city=c['id'],count=10,source='garrison'))['ok'])

    def rally_world(self):
        w=World(1,{'bandit_cap':0})
        # Existing primary parties remain home patrols; second parties actually march.
        self.apply(w,0,decide(w.observe(0)))
        cmds=decide(w.observe(0));self.assertFalse(any(c['type']=='assemble' for c in cmds))
        self.apply(w,0,cmds)
        rally=[u for u in w.units.values() if (u['order'] or {}).get('campaign_phase')=='rally']
        self.assertGreaterEqual(len(rally),2)
        for u in rally:
            c=w.cities[u['order']['rally_city']];u.update(x=c['x'],y=c['y'],path=[],healthy=100,food=300000)
        return w,rally

    def test_rally_siege_disband_and_return_cycle(self):
        w,rally=self.rally_world();cmds=decide(w.observe(0))
        self.assertEqual(sum(c['type']=='assemble' for c in cmds),1)
        self.apply(w,0,cmds);self.assertEqual(len(w.armies),1)
        members=[w.units[i] for i in next(iter(w.armies.values()))];target=w.cities[members[0]['army_target']]
        for u in members:u.update(x=target['x']-1200,y=target['y'],path=[])
        w.update_known();self.apply(w,0,decide(w.observe(0)))
        self.assertTrue(all(u['order']['type']=='siege' for u in members))
        for _ in range(300):
            w.step()
            if target['nation']==0:break
        self.assertEqual(target['nation'],0)
        cmds=decide(w.observe(0));self.assertEqual(sum(c['type']=='disband' for c in cmds),1)
        self.apply(w,0,cmds);self.assertFalse(w.armies)
        for u in members:
            self.assertIsNone(u['army'])
            self.assertTrue((u['order'] or {}).get('campaign_phase')=='return' or w.city_at(u))
        w.check()

    def test_cancel_rally_when_front_target_changes(self):
        w,rally=self.rally_world();target=rally[0]['order']['campaign_target']
        w.capture(target,0,[0]);w.update_known()
        cmds=decide(w.observe(0))
        self.assertFalse(any(c['type']=='assemble' for c in cmds))
        self.apply(w,0,cmds)
        self.assertFalse(any((u['order'] or {}).get('campaign_phase')=='rally' for u in rally))

    def test_strong_city_can_trigger_preparation_before_full_strength(self):
        w=World(1,{'bandit_cap':0})
        self.apply(w,0,decide(w.observe(0)))
        obs=w.observe(0)
        for c in obs['cities']:
            if c['nation']!=0:c['healthy']=300
        cmds=decide(obs)
        self.assertTrue(any(c.get('campaign_phase')=='rally' for c in cmds))
        self.assertFalse(any(c['type']=='assemble' for c in cmds))
