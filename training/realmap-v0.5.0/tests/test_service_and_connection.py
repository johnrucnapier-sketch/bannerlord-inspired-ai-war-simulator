import asyncio
import json
import unittest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from tests.legacy_world import LegacyWorld as World
from aiwar.server import Session

class CityService(unittest.TestCase):
    def setup_city(self):
        w=World(1,{'expansion_reserve':0});c=w.cities['c00'];g=w.units[c['garrison']]
        u=next(u for u in w.units.values() if u['kind']=='party' and u['clan']==0)
        u.update(healthy=80,wounded=20,food=1000,last_battle=10)
        c.update(recruits=100,food=1000000)
        return w,c,g,u

    def test_unload_then_recruit_then_fill_conserves_resources(self):
        w,c,g,u=self.setup_city();total=w.size(u)+w.size(g)+c['recruits'];food=c['food']+u['food']
        w.arrivals()
        self.assertEqual((u['healthy'],u['wounded'],g['wounded'],c['recruits']),(150,0,20,30))
        self.assertEqual(u['food'],w.food_cap(u))
        self.assertEqual(w.size(u)+w.size(g)+c['recruits'],total)
        self.assertEqual(c['food']+u['food'],food)
        before=(w.size(u),w.size(g),c['recruits'],c['food'],u['food'])
        w.arrivals();self.assertEqual(before,(w.size(u),w.size(g),c['recruits'],c['food'],u['food']))
        w.check()

    def test_full_garrison_and_limited_resources_do_not_create_troops(self):
        w,c,g,u=self.setup_city();g['healthy']=495;c.update(recruits=2,food=100)
        w.arrivals()
        self.assertEqual((g['wounded'],u['wounded'],u['healthy']),(5,15,82))
        self.assertEqual((c['recruits'],c['food'],u['food']),(0,0,1100));w.check()

    def test_battle_siege_and_enemy_city_cannot_service(self):
        for case in ('battle','siege','enemy'):
            w,c,g,u=self.setup_city()
            if case=='battle':u['battle']='test'
            if case=='siege':w.battles['test']={'city':c['id']}
            if case=='enemy':c['nation']=1
            w.service_party(u,c)
            self.assertEqual((u['healthy'],u['wounded'],u['food']),(80,20,1000))

    def test_legacy_rules_do_not_auto_service(self):
        w,c,g,u=self.setup_city();w.cfg.pop('auto_city_service')
        w.service_party(u,c);self.assertEqual(u['wounded'],20)

    def test_regulars_reduce_losses_without_buffing_country_wars(self):
        def fight(multiplier,enemy_nation):
            w=World(1,{'regular_vs_bandit':multiplier});w.units.clear();w.cities.clear()
            a=w.new_unit('party',0,0,30,60000,40000)
            b=w.new_unit('bandit' if enemy_nation==-1 else 'party',enemy_nation,6,20,60000,40000)
            w.start_battle(a,b)
            for hour in range(1,200):
                w.hour=hour;w.battle_tick()
                if not w.battles:break
            return a['healthy'],a['wounded']
        old=fight(1,-1);new=fight(3,-1)
        self.assertLessEqual(30-new[0],(30-old[0])/2)
        self.assertEqual(fight(1,1),fight(3,1))

class ConnectionSafety(unittest.IsolatedAsyncioTestCase):
    def test_heartbeat_timeout_resets_credit(self):
        s=Session(1);s.viewers['viewer']=10;s.paused=False;s.credit=100
        s.check_viewers(13.1)
        self.assertTrue(s.paused);self.assertEqual(s.credit,0)
        s.viewers['viewer']=14;s.check_viewers(14)
        self.assertTrue(s.paused)

    async def test_real_disconnect_pauses_even_with_diagnostic_client(self):
        s=Session(1)
        async with serve(s.handle,'127.0.0.1',0) as server:
            port=server.sockets[0].getsockname()[1];url=f'ws://127.0.0.1:{port}'
            loop=asyncio.create_task(s.loop())
            async def command(ws,payload):
                await ws.send(json.dumps(payload))
                while True:
                    r=json.loads(await asyncio.wait_for(ws.recv(),2))
                    if r.get('type')=='ack' and r.get('action')==payload['type']:
                        self.assertTrue(r['ok']);return
            try:
                async with connect(url) as diagnostic:
                    async with connect(url) as viewer:
                        await command(viewer,{'type':'viewer'})
                        await command(viewer,{'type':'pause','value':False})
                        await asyncio.sleep(.15)
                        self.assertGreater(s.world.hour,0)
                    await asyncio.sleep(.1)
                    self.assertTrue(s.paused);hour=s.world.hour
                    await asyncio.sleep(.1);self.assertEqual(s.world.hour,hour)
                    async with connect(url) as reconnected:
                        await command(reconnected,{'type':'viewer'})
                        self.assertTrue(s.paused)
                        await command(reconnected,{'type':'pause','value':False})
                        self.assertFalse(s.paused)
            finally:
                s.shutdown=True;await loop

    async def test_send_failure_pauses_and_closes_socket_for_reconnect(self):
        import time
        s=Session(1)
        class BrokenViewer:
            closed=False
            async def send(self,message):raise OSError('broken transport')
            async def close(self,**kwargs):self.closed=True;s.shutdown=True
        ws=BrokenViewer();s.clients[ws]=None;s.viewers[ws]=time.monotonic();s.paused=False
        await asyncio.wait_for(s.loop(),2)
        self.assertTrue(ws.closed);self.assertTrue(s.paused)
        self.assertNotIn(ws,s.viewers)
