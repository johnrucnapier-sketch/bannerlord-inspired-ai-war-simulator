"""Local viewer bridge. The viewer never executes the world rules."""
import argparse
import asyncio
import json
import time
import secrets
from datetime import datetime,timezone
from . import __version__
from pathlib import Path
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from .engine import World
from .policies import decision_cycle

ROOT=Path(__file__).resolve().parent.parent

class Session:
    def __init__(self,seed=None):
        self.world=World(seed if seed is not None else secrets.randbelow(2147483646)+1)
        self.paused=True
        self.speed=24 # game hours / wall second; 20 years ~28 minutes
        self.styles=['march','march']
        self.clients={}
        self.viewers={}
        self.pause_reason=""
        self.credit=0.0
        self.shutdown=False
        self.last_decision=-1
        self.replaying=None
        self.replay_index=0
        self.run_id=secrets.token_hex(6)
        self.archived=False
        self.style_history=[{'hour':0,'styles':self.styles.copy()}]

    def record_run(self,reason):
        if self.archived:return
        out=ROOT/'artifacts/run-history.jsonl';out.parent.mkdir(exist_ok=True)
        with out.open('a',encoding='utf-8') as f:
            f.write(json.dumps({'run_id':self.run_id,'utc':datetime.now(timezone.utc).isoformat(),
                'version':__version__,'mode':self.world.cfg.get('mode','duel'),'seed':self.world.seed,'hour':self.world.hour,
                'style_history':self.style_history,'reason':reason,'result':self.world.result,
                'physics_digest':self.world.physics_digest()},ensure_ascii=False)+'\n')
        self.archived=True

    def reset(self,seed=None,mode=None):
        mode = mode or self.world.cfg.get("mode", "duel")
        if mode not in ("duel", "rural"):raise ValueError("未知游戏模式")
        if seed is None:
            seed=secrets.randbelow(2147483646)+1
            while seed==self.world.seed:seed=secrets.randbelow(2147483646)+1
        if type(seed) is not int or not 1<=seed<=2147483647:raise ValueError('种子须为1至2147483647的整数')
        self.record_run('new_game')
        if mode != self.world.cfg.get('mode','duel'):
            self.styles=['guard','manual'] if mode=='rural' else ['march','march']
        self.world=World(seed,{"mode":mode});self.paused=True;self.credit=0;self.last_decision=-1;self.replaying=None
        self.run_id=secrets.token_hex(6);self.archived=False
        self.style_history=[{'hour':0,'styles':self.styles.copy()}]

    def snapshot(self,view):
        obs=self.world.observe(view)
        obs.update(mode=self.world.cfg.get('mode','duel'),rural_score=self.world.rural_score() if self.world.cfg.get('mode')=='rural' else None)
        if self.world.cfg.get('mode')=='rural':
            totals=[t for t in self.world.observer_totals() if t['nation']==0]
        else:totals=self.world.observer_totals()
        obs.update(paused=self.paused,pause_reason=self.pause_reason,speed=self.speed,styles=self.styles,version=__version__,rule_version=self.world.cfg['version'],replaying=self.replaying is not None,run_id=self.run_id,seed=self.world.seed,observer_totals=totals,observer_events=self.world.observer_events())
        return obs

    def advance(self):
        if self.replaying is not None:
            journal=self.replaying.commands
            while self.replay_index<len(journal) and journal[self.replay_index]['hour']==self.world.hour:
                item=journal[self.replay_index]
                self.world.command(item['nation'],item['command'])
                self.replay_index+=1
            if self.world.hour<self.replaying.hour:
                self.world.step()
            if self.world.hour>=self.replaying.hour:
                while self.replay_index<len(journal) and journal[self.replay_index]['hour']==self.world.hour:
                    item=journal[self.replay_index]
                    self.world.command(item['nation'],item['command'])
                    self.replay_index+=1
                matches=self.world.physics_digest()==self.replaying.physics_digest()
                self.paused=True
                self.replaying=None
                self.styles=['manual','manual']
                print('VIEWER_REPLAY_OK' if matches else 'VIEWER_REPLAY_MISMATCH',flush=True)
            return
        if self.world.hour%self.world.cfg['decision_hours']==0 and self.last_decision!=self.world.hour:
            decision_cycle(self.world,self.styles)
            self.last_decision=self.world.hour
        self.world.step()
        if self.world.result:
            self.paused=True
            self.record_run('finished')

    def pause_for_disconnect(self):
        self.paused=True
        self.credit=0
        self.pause_reason='界面连接中断，模拟已自动暂停；连接恢复后请点继续'

    def drop_client(self,ws):
        self.clients.pop(ws,None)
        if ws in self.viewers:
            self.viewers.pop(ws,None)
            self.pause_for_disconnect()

    def check_viewers(self,now=None):
        now=time.monotonic() if now is None else now
        if not self.viewers or any(now-last>3 for last in self.viewers.values()):
            if not self.paused:self.pause_for_disconnect()

    async def handle(self,ws):
        self.clients[ws]=None
        try:
            async for raw in ws:
                try:
                    msg=json.loads(raw)
                    def integers(v):
                        if isinstance(v,float) and v.is_integer():return int(v)
                        if isinstance(v,dict):return {k:integers(x) for k,x in v.items()}
                        if isinstance(v,list):return [integers(x) for x in v]
                        return v
                    msg=integers(msg)
                    op=msg.get('type')
                    if op=='viewer':
                        self.viewers[ws]=time.monotonic()
                        self.paused=True;self.credit=0
                    elif op=='heartbeat':
                        if ws in self.viewers:self.viewers[ws]=time.monotonic()
                        continue
                    elif op=='view':
                        view=msg.get('nation')
                        if view not in (None,0,1):
                            raise ValueError('视角无效')
                        self.clients[ws]=view
                    elif op=='pause':
                        resume=not bool(msg.get('value',True))
                        if resume and (ws not in self.viewers or time.monotonic()-self.viewers[ws]>3):
                            raise ValueError('请在已连接的观察界面点击继续')
                        self.paused=not resume;self.credit=0
                        if resume:self.pause_reason='' 
                    elif op=='speed':
                        self.speed=max(1,min(2400,int(msg['value'])))
                    elif op=='step':
                        self.paused=True;self.credit=0;self.advance()
                    elif op=='reset':
                        self.reset(msg.get('seed'),msg.get('mode'))
                    elif op=='save':
                        self.world.save(ROOT/'artifacts/session.save.json')
                        (ROOT/'artifacts/session.control.json').write_text(json.dumps({'styles':self.styles,'last_decision':self.last_decision,'style_history':self.style_history}))
                    elif op=='replay':
                        self.record_run('replay')
                        self.replaying=World.load(ROOT/'artifacts/session.save.json')
                        self.run_id=secrets.token_hex(6);self.archived=True
                        self.world=World(self.replaying.seed,self.replaying.cfg)
                        self.replay_index=0;self.last_decision=-1;self.credit=0;self.paused=False
                    elif op=='load':
                        loaded=World.load(ROOT/'artifacts/session.save.json')
                        self.record_run('load')
                        self.run_id=secrets.token_hex(6);self.archived=False
                        self.world=loaded;self.paused=True;self.credit=0;self.replaying=None
                        side=ROOT/'artifacts/session.control.json'
                        state=json.loads(side.read_text()) if side.exists() else {}
                        self.styles=state.get('styles',['manual','manual'])
                        self.last_decision=state.get('last_decision',self.world.hour)
                        self.style_history=state.get('style_history',[{'hour':self.world.hour,'styles':self.styles.copy()}])
                    elif op=='style':
                        n=msg['nation'];style=msg['style']
                        if n not in (0,1) or style not in ('manual','march','guard','p1','p2','p3','p4'):
                            raise ValueError('控制器无效')
                        self.styles[n]=style
                        self.style_history.append({'hour':self.world.hour,'styles':self.styles.copy()})
                    elif op=='command':
                        if self.replaying is not None:raise ValueError('重放期间不能修改命令')
                        result=self.world.command(msg['nation'],msg['command'])
                        await ws.send(json.dumps({'type':'ack',**result},ensure_ascii=False));continue
                    elif op=='ping':
                        pass
                    else:
                        raise ValueError('未知请求')
                    await ws.send(json.dumps({'type':'ack','ok':True,'action':op},ensure_ascii=False))
                    await ws.send(json.dumps({'type':'state','data':self.snapshot(self.clients[ws])},ensure_ascii=False))
                except (ValueError,KeyError,TypeError,OSError) as exc:
                    await ws.send(json.dumps({'type':'ack','ok':False,'error':str(exc)},ensure_ascii=False))
        except ConnectionClosed:
            pass  # Closing the viewer is a normal disconnect, including abrupt OS closure.
        finally:
            self.drop_client(ws)

    async def loop(self):
        last=time.monotonic();last_send=0
        while not self.shutdown:
            now=time.monotonic();delta=min(0.25,now-last);last=now
            self.check_viewers(now)
            if not self.paused:
                self.credit+=delta*self.speed
                # Bound work per slice so pause/input remain responsive under load.
                deadline=time.monotonic()+0.025
                while self.credit>=1 and not self.paused and time.monotonic()<deadline:
                    self.advance();self.credit-=1
            if now-last_send>=0.1:
                last_send=now
                cache={}
                for ws,view in list(self.clients.items()):
                    if view not in cache:
                        cache[view]=json.dumps({'type':'state','data':self.snapshot(view)},ensure_ascii=False)
                    try:
                        await asyncio.wait_for(ws.send(cache[view]),timeout=0.2)
                    except Exception:
                        self.drop_client(ws)
                        try:
                            await asyncio.wait_for(ws.close(code=1011,reason="状态发送失败，请重新连接"),timeout=0.5)
                        except Exception:
                            pass
            await asyncio.sleep(0.005)

async def start(port,seed):
    session=Session(seed)
    async with serve(session.handle,'127.0.0.1',port,max_size=1_000_000):
        print(f'AIWAR_READY ws://127.0.0.1:{port}',flush=True)
        await session.loop()

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=18765);p.add_argument('--seed',type=int,default=None)
    a=p.parse_args()
    try:
        asyncio.run(start(a.port,a.seed))
    except KeyboardInterrupt:
        pass

if __name__=='__main__': main()
