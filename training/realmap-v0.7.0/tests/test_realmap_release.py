import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from aiwar.engine import World
from aiwar import military,real_map
from aiwar.server import Session
from aiwar.strategy_catalog import catalog

class ReleaseBoundaries(unittest.TestCase):
    def test_missing_pack_does_not_replace_current_session(self):
        s=Session(7);old=s.world;before=old.physics_digest()
        try:
            with tempfile.TemporaryDirectory() as td,patch.object(real_map,'ROOT',Path(td)),patch.object(s,'record_run') as archive:
                with self.assertRaisesRegex(ValueError,'未安装'):s.reset(8,'realmap')
                archive.assert_not_called()
            self.assertIs(s.world,old);self.assertEqual(s.world.physics_digest(),before)
        finally:s.strategy_runtime.close()

    def test_settlement_or_clan_change_rejects_load_and_replay_init(self):
        w=World(1,{'mode':'realmap'})
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'state.json';w.save(p)
            for name in ('settlements.json','clans.json'):
                altered=dict(real_map.map_hashes());altered[name]='0'*64
                with patch.object(real_map,'map_hashes',return_value=altered):
                    with self.assertRaisesRegex(ValueError,'数据版本不匹配'):World.load(p)
                    with self.assertRaisesRegex(ValueError,'数据版本不匹配'):World(w.seed,w.cfg)

    def test_recapture_recovers_slot_in_normal_arrival_tick(self):
        w=World(1,{'mode':'realmap'});c=next(c for c in w.cities.values() if any(w.cities[i]['nation']==c['nation'] for i in c['supply_neighbors']))
        d=next(w.cities[i] for i in c['supply_neighbors'] if w.cities[i]['nation']==c['nation'])
        r=w.command(c['nation'],dict(type='dispatch',city=c['id'],destination=d['id'],food=0));u=w.units[r['unit']]
        owners={k:x['nation'] for k,x in w.cities.items()}
        for x in w.cities.values():x['nation']=1-u['nation']
        military.resume(w,u)
        for k,x in w.cities.items():x['nation']=owners[k]
        u.update(x=d['x'],y=d['y'])
        military.arrival(w,u);self.assertEqual(c['convoy'],u['id']);self.assertTrue(u['path']);w.check()

    def test_no_archive_means_no_broken_historical_entries(self):
        with tempfile.TemporaryDirectory() as td,patch('aiwar.strategy_catalog.ARCHIVE',Path(td)):
            self.assertFalse(any(s['external'] for s in catalog('duel')))
            self.assertTrue(any(s['id']=='march' for s in catalog('realmap')))

if __name__=='__main__':unittest.main()
