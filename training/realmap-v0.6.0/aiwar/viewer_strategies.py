"""Persistent, separate JSONL agents for the local historical strategy viewer."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from .match import JsonAgent
from .policies import decide
from .strategy_catalog import ROOT, EXTERNAL, verify_source

class ViewerStrategies:
    def __init__(self):
        self.agents={};self.logs={};self.keys={};self.previous=[[],[]]

    def close(self):
        for agent in self.agents.values():agent.close()
        for log in self.logs.values():log.close()
        self.agents.clear();self.logs.clear();self.keys.clear();self.previous=[[],[]]

    def cycle(self,world,styles,run_id):
        nations=(0,) if world.cfg.get('mode')=='rural' else (0,1)
        observations={n:world.observe(n) for n in nations}
        requests={n:dict(protocol_version=1,type='decide',request_id=f'{n}:{world.hour}',
                        observation=observations[n],previous_outcomes=self.previous[n]) for n in nations}
        for n in nations:
            style=styles[n]
            if style not in EXTERNAL:continue
            if self.keys.get(n)!=style:
                if n in self.agents:self.agents.pop(n).close();self.logs.pop(n).close()
                verify_source(style)
                folder=ROOT/'artifacts/viewer-agents'/run_id;folder.mkdir(parents=True,exist_ok=True)
                log=(folder/f'{n}-{style}.stderr.log').open('ab')
                self.logs[n]=log
                self.agents[n]=JsonAgent([sys.executable,'-I',str(ROOT/'scripts/viewer_strategy_agent.py'),style],log,timeout=2)
                self.keys[n]=style
        replies={}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={n:pool.submit(self.agents[n].decide,requests[n]) for n in nations if styles[n] in EXTERNAL}
            for n in nations:
                if n not in futures:replies[n]=(decide(observations[n],styles[n]),None)
            replies.update({n:f.result() for n,f in futures.items()})
        errors=[f'{styles[n]}: {error}' for n,(_,error) in replies.items() if error]
        # Some historical Grok agents catch their own exception and return []; preserve
        # their original behavior but surface stderr in the viewer instead of hiding it.
        for n,log in self.logs.items():
            log.flush()
            size=log.tell()
            key=(n,'stderr_size')
            previous=self.keys.get(key,0)
            if size>previous:
                with open(log.name,'rb') as source:
                    source.seek(previous);tail=source.read()
                if b'Traceback (most recent call last)' in tail:errors.append(f'{styles[n]}: 内部异常，详见策略日志')
            self.keys[key]=size
        if errors:
            for error in errors:world.emit('policy_error','历史策略异常，演示已暂停',error=error)
            raise ValueError('；'.join(errors))
        self.previous=[[],[]]
        for n in nations:
            self.previous[n]=[world.command(n,command) for command in replies[n][0]]
        return [r for batch in self.previous for r in batch]
