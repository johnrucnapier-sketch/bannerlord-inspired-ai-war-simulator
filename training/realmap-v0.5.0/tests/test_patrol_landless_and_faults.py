import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
from aiwar.engine import World
from aiwar.patrols import PATROLS,decide as patrol
from aiwar.policies import decide
from aiwar.server import Session

class LandlessPatrolTests(unittest.TestCase):
    def test_lost_last_clan_city(self):
        w=World(1)
        original={u['id'] for u in w.units.values() if u['kind']=='party' and u['clan']==0}
        w.capture('c00',1,[6]);w.update_known()
        for style in PATROLS:
            for command in patrol(w.observe(0),style):
                self.assertTrue(w.command(0,command)['ok'],(style,command))
        self.assertTrue(original <= set(w.units))
        self.assertEqual(w.cities['c00']['nation'],1)
        self.assertTrue(all(w.units[u]['nation']==0 for u in original))
        for c in decide(w.observe(0),'march_p5'):self.assertTrue(w.command(0,c)['ok'])
        for c in list(w.cities.values()):
            if c['nation']==0:w.capture(c['id'],1,[6])
        for style in PATROLS:self.assertEqual(patrol(w.observe(0),style),[])

class CoreFaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_decision_keeps_websocket_and_preserves_state(self):
        with tempfile.TemporaryDirectory() as directory,patch('aiwar.server.ROOT',Path(directory)):
            s=Session(1);s.styles=['march_p5','march'];before=s.world.physics_digest()
            async with serve(s.handle,'127.0.0.1',0) as server:
                port=server.sockets[0].getsockname()[1]
                async with connect(f'ws://127.0.0.1:{port}') as ws:
                    with patch('aiwar.server.decision_cycle',side_effect=StopIteration('landless regression')):
                        await ws.send(json.dumps({'type':'step'}))
                        ack=json.loads(await ws.recv());state=json.loads(await ws.recv())
                    self.assertTrue(ack['ok']);self.assertEqual(state['type'],'state')
                    self.assertTrue(s.paused and s.faulted)
                    self.assertIn('StopIteration',state['data']['pause_reason'])
                    self.assertEqual(s.world.physics_digest(),before)
                    s.advance();self.assertEqual(s.world.hour,0)
                    await ws.send(json.dumps({'type':'ping'}))
                    self.assertTrue(json.loads(await ws.recv())['ok']);await ws.recv()
                    await ws.send(json.dumps({'type':'pause','value':False}))
                    self.assertFalse(json.loads(await ws.recv())['ok'])
                    await ws.send(json.dumps({'type':'reset','seed':2}))
                    self.assertTrue(json.loads(await ws.recv())['ok']);await ws.recv()
                    self.assertFalse(s.faulted)
            save=next(Path(directory).glob('artifacts/faults/*/state.save.json'))
            self.assertEqual(World.load(save).physics_digest(),before)
            report=json.loads((save.parent/'control.json').read_text())
            self.assertTrue(report['valid_state'])
