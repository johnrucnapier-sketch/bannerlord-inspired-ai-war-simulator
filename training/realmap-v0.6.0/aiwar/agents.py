"""Persistent policy processes, equal observation snapshots and bounded decisions.
This is an API boundary, not a sandbox for hostile Python modules.
"""
import importlib
import multiprocessing as mp
import time
from multiprocessing.connection import wait


def _worker(pipe,module,style):
    try:
        decide=importlib.import_module(module).decide
        while True:
            observation=pipe.recv()
            if observation is None:break
            try:
                result=decide(observation,style)
                pipe.send({'commands':result[:100] if isinstance(result,list) else [],'error':None})
            except Exception as e:
                pipe.send({'commands':[],'error':type(e).__name__+': '+str(e)})
    except (EOFError,BrokenPipeError):pass
    finally:pipe.close()


class PolicyPool:
    def __init__(self,modules=('aiwar.policies','aiwar.policies'),styles=('march','march'),timeout=2):
        self.ctx=mp.get_context('spawn')
        self.modules=list(modules);self.styles=list(styles);self.timeout=timeout
        self.processes={};self.pipes={}
        for n in (0,1):self._start(n)

    def _start(self,n):
        parent,child=self.ctx.Pipe()
        p=self.ctx.Process(target=_worker,args=(child,self.modules[n],self.styles[n]),daemon=True)
        p.start();child.close();self.processes[n]=p;self.pipes[n]=parent

    def _stop(self,n):
        p=self.processes[n]
        if p.is_alive():p.terminate()
        p.join(timeout=2)
        if p.is_alive():p.kill();p.join()
        self.pipes[n].close()

    def cycle(self,world):
        observations=[world.observe(n) for n in (0,1)]
        results=[None,None]
        pending={}
        start=time.monotonic()
        for n in (0,1):
            if self.styles[n]=='manual':
                results[n]={'commands':[],'error':None};continue
            try:
                self.pipes[n].send(observations[n]);pending[self.pipes[n]]=n
            except (BrokenPipeError,EOFError,OSError):
                results[n]={'commands':[],'error':'process exited'}
                self._stop(n);self._start(n)
        while pending:
            ready=wait(list(pending),timeout=max(0,self.timeout-(time.monotonic()-start)))
            if not ready:break
            for pipe in ready:
                n=pending.pop(pipe)
                try:results[n]=pipe.recv()
                except (EOFError,OSError):results[n]={'commands':[],'error':'process exited'}
        for pipe,n in pending.items():
            results[n]={'commands':[],'error':'decision timeout'}
            self._stop(n);self._start(n)
        answers=[]
        for n,result in enumerate(results):
            if result['error']:
                world.emit('policy_error',f'国家{n}策略失败，保持原命令',error=result['error'])
            for cmd in result['commands']:
                answers.append(world.command(n,cmd))
        return answers

    def close(self):
        for n in (0,1):self._stop(n)
