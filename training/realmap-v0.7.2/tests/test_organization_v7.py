import unittest
from aiwar.engine import World
from aiwar import organization

class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.w=World(1,{'mode':'realmap','bandit_cap':0,'auto_city_service':False})
        self.n=0;self.king=self.w.nations['0']['ruler_clan']
        self.leader=next(u for u in self.w.units.values() if u['kind']=='party' and u['clan']==self.king)
        self.leader['healthy']=150
    def party(self,predicate):
        p=next(u for u in self.w.units.values() if u['nation']==self.n and u['kind']=='party' and predicate(u))
        p.update(x=self.leader['x'],y=self.leader['y'],healthy=110,wounded=0)
        return p
    def test_low_tier_one_slot_can_support_ruler_despite_ready(self):
        p=self.party(lambda u:self.w.clan_party_limit(u['clan'])==1)
        p['healthy']=150;home=organization.home(self.w,p['clan']);self.w.units[home['garrison']]['healthy']=300
        self.assertTrue(organization.ready(self.w,p['clan']))
        result=self.w.command(0,dict(type='assemble',unit=self.leader['id'],units=[p['id']]))
        self.assertTrue(result['ok'],result);self.w.check()
    def test_non_ruler_cannot_accept_foreign_support(self):
        p=self.party(lambda u:self.w.clan_party_limit(u['clan'])==1)
        leader=self.party(lambda u:u['clan']!=self.king and self.w.clan_party_limit(u['clan'])>=2)
        result=self.w.command(0,dict(type='assemble',unit=leader['id'],units=[p['id']]))
        self.assertFalse(result['ok'])
    def test_support_requires_strength_and_no_second_detachment(self):
        p=self.party(lambda u:self.w.clan_party_limit(u['clan'])==1);p['healthy']=99
        self.assertFalse(organization.can_support(self.w,p,self.leader))
        p['healthy']=104;self.assertFalse(organization.can_support(self.w,p,self.leader))
        p['healthy']=105;self.assertTrue(organization.can_support(self.w,p,self.leader))
    def test_at_most_one_army_per_clan(self):
        peers=[u for u in self.w.units.values() if u['kind']=='party' and u['clan']==self.king]
        result=self.w.command(0,dict(type='assemble',unit=peers[0]['id'],units=[peers[1]['id']]))
        self.assertTrue(result['ok'])
        with self.assertRaises(ValueError):organization.validate_assembly(self.w,peers[2],[peers[2]])
    def test_missing_current_party_is_not_one_slot_exception(self):
        p=self.party(lambda u:u['clan']!=self.king and self.w.clan_party_limit(u['clan'])>=2)
        for u in list(self.w.units.values()):
            if u['kind']=='party' and u['clan']==p['clan'] and u['id']!=p['id']:self.w.remove(u['id'])
        p['healthy']=150;home=organization.home(self.w,p['clan']);self.w.units[home['garrison']]['healthy']=300
        self.assertTrue(organization.ready(self.w,p['clan']))
        self.assertFalse(organization.can_support(self.w,p,self.leader))
    def test_caps_and_source_clan_metadata(self):
        expected=[18,17,18,18,20,19,18,18]
        for n,count in enumerate(expected):
            self.assertEqual(sum(u['nation']==n and u['kind']=='party' for u in self.w.units.values()),count)
        self.assertEqual(len(self.w.map_clans),73)
        self.assertTrue(all('tier' in c and not c.get('provenance','').startswith('owner_id_from_map') for c in self.w.map_clans.values()))

if __name__=='__main__':unittest.main()
