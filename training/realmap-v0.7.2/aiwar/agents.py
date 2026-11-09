"""Persistent policy processes, equal observation snapshots and bounded decisions.
This is an API boundary, not a sandbox for hostile Python modules.
"""
import importlib
import multiprocessing as mp
import os
import pickle
import queue
import signal
import subprocess
import time
import threading
from multiprocessing.connection import wait
from .sdk import command_error, MAX_COMMANDS


PROCESS_CLEANUP_TIMEOUT = .2
MAX_POLICY_RESPONSE_BYTES = 1_048_576


def _kill_process_tree(pid, timeout=PROCESS_CLEANUP_TIMEOUT):
    """Best-effort cleanup of ordinary children, not hostile-code containment.

    POSIX workers own a session/process group. Descendants that create a new
    session/group escape it. Windows taskkill /T is supported but is not a Job
    Object: detached/reparented children or an already-exited root can escape.
    The caller must also kill/reap the direct process, with a bounded wait.
    """
    if os.name == 'posix':
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass
    elif os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=max(.001, timeout),
                           check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _worker(pipe,module,style):
    try:
        if os.name == 'posix':
            os.setsid()  # Before importing policy code or creating descendants.
        decide=importlib.import_module(module).decide
        while True:
            observation=pipe.recv()
            if observation is None:break
            try:
                result=decide(observation,style)
                if type(result) is not list or len(result)>MAX_COMMANDS:
                    raise ValueError('policy must return a list of at most 100 commands')
                pipe.send({'commands':result,'error':None,'completed_at':time.monotonic()})
            except Exception as e:
                pipe.send({'commands':[],'error':type(e).__name__+': '+str(e),'completed_at':time.monotonic()})
    except (EOFError,BrokenPipeError):pass
    finally:pipe.close()


class _PolicyConnection:
    """One cancellable-lifecycle I/O worker per policy generation.

    Neither sending a large observation nor receiving a partial framed reply
    may run on the match thread. wait() sees only our one-byte completion
    notification, never raw policy pipe readiness. As with JsonAgent, an
    escaped pipe holder can defer restart, but cannot accumulate workers or
    block the host. Pickled policy IPC remains a trusted-code API, not a sandbox.
    """
    def __init__(self, pipe, ctx):
        self.pipe = pipe
        self.notice_read, self.notice_write = ctx.Pipe(duplex=False)
        self.requests = queue.Queue(maxsize=1)
        self.stopped = threading.Event()
        self.result = None
        self.thread = threading.Thread(target=self._exchange, name='policy-exchange', daemon=True)
        self.thread.start()

    def _exchange(self):
        try:
            while True:
                observation = self.requests.get()
                if observation is None or self.stopped.is_set():
                    break
                try:
                    self.pipe.send(observation)
                    result = pickle.loads(self.pipe.recv_bytes(MAX_POLICY_RESPONSE_BYTES))
                except (EOFError, OSError, ValueError, pickle.UnpicklingError) as exc:
                    result = {'commands': [], 'error': 'process communication failed: ' + str(exc),
                              'completed_at': time.monotonic()}
                if self.stopped.is_set():
                    break
                self.result = result
                self.notice_write.send_bytes(b'1')
        except (EOFError, OSError):
            pass
        finally:
            self.pipe.close()
            self.notice_write.close()

    def send(self, observation):
        if self.stopped.is_set():
            raise OSError('previous process cleanup pending; restart deferred')
        self.requests.put_nowait(observation)

    def recv(self):
        self.notice_read.recv_bytes(1)
        return self.result

    def fileno(self):
        return self.notice_read.fileno()

    def close(self):
        self.stopped.set()
        try:
            self.requests.put_nowait(None)
        except queue.Full:
            pass
        self.notice_read.close()

    def join(self, timeout):
        self.thread.join(timeout=max(0, timeout))
        return not self.thread.is_alive()


class PolicyPool:
    def __init__(self,modules=None,styles=('march','march'),timeout=2):
        self.ctx=mp.get_context('spawn')
        self.styles=list(styles);self.modules=list(modules or ['aiwar.policies']*len(self.styles));self.timeout=timeout
        if not self.styles or len(self.modules)!=len(self.styles):raise ValueError('one module and style required per nation')
        if timeout<=0:raise ValueError('timeout must be positive')
        self.nations=tuple(range(len(self.styles)))
        self.metrics=[dict(decisions=0,errors=0,timeouts=0,invalid_commands=0,malformed_commands=0) for _ in self.nations]
        self.last_timings={}
        self.processes={};self.pipes={};self._stopping=set()
        for n in self.nations:self._start(n)

    def _start(self,n):
        parent,child=self.ctx.Pipe()
        p=self.ctx.Process(target=_worker,args=(child,self.modules[n],self.styles[n]),daemon=True)
        p.start();child.close();self.processes[n]=p;self.pipes[n]=_PolicyConnection(parent,self.ctx)

    def _stop(self,n):
        p=self.processes.get(n)
        if p is None:return True
        deadline=time.monotonic()+(PROCESS_CLEANUP_TIMEOUT if n not in self._stopping else 0)
        pipe=self.pipes[n]
        if n not in self._stopping:
            self._stopping.add(n)
            _kill_process_tree(p.pid)
            if p.is_alive():p.kill()
            pipe.close()
        p.join(timeout=max(0,deadline-time.monotonic()))
        io_done=pipe.join(max(0,deadline-time.monotonic()))
        if p.is_alive() or not io_done:
            # No new process/thread until this retired generation is released.
            return False
        p.close()
        self.processes.pop(n,None);self.pipes.pop(n,None);self._stopping.discard(n)
        return True

    def cycle(self,world):
        if tuple(world.nation_ids())!=self.nations:raise ValueError('policy pool does not match world nations')
        observations=[world.observe(n) for n in self.nations]
        results=[None for _ in self.nations]
        pending={}
        self.last_timings={}
        restart=set()
        for n in self.nations:
            if self.styles[n]=='manual' or (world.cfg.get('mode')=='rural' and n!=0):
                results[n]={'commands':[],'error':None};continue
            self.metrics[n]['decisions']+=1
            try:
                if n not in self.pipes:raise OSError('previous process cleanup pending')
                self.pipes[n].send(observations[n])
                submitted=time.monotonic()
                self.last_timings[n]={'submitted_at':submitted,'deadline':submitted+self.timeout}
                pending[self.pipes[n]]=n
            except (BrokenPipeError,EOFError,OSError) as exc:
                results[n]={'commands':[],'error':str(exc) or 'process exited'}
                restart.add(n)
        while pending:
            deadline=min(self.last_timings[n]['deadline'] for n in pending.values())
            ready=wait(list(pending),timeout=max(0,deadline-time.monotonic()))
            for pipe in ready:
                n=pending.pop(pipe)
                try:
                    result=pipe.recv()
                    completed=result.get('completed_at',time.monotonic())
                    self.last_timings[n]['completed_at']=completed
                    if completed>self.last_timings[n]['deadline']:
                        result={'commands':[],'error':'decision timeout'}
                        restart.add(n)
                    results[n]=result
                    if result.get('error','') and result['error'].startswith('process communication failed:'):
                        restart.add(n)
                except (EOFError,OSError):
                    results[n]={'commands':[],'error':'process exited'}
                    restart.add(n)
            now=time.monotonic()
            for pipe,n in list(pending.items()):
                if now>=self.last_timings[n]['deadline']:
                    results[n]={'commands':[],'error':'decision timeout'}
                    pending.pop(pipe);restart.add(n)
        # Restart only after all deadlines have been collected, so cleanup time
        # for one failed nation cannot consume another nation's decision budget.
        for n in sorted(restart):
            if self._stop(n):self._start(n)
        answers=[]
        for n,result in enumerate(results):
            if result['error']:
                self.metrics[n]['errors']+=1
                self.metrics[n]['timeouts']+=result['error']=='decision timeout'
                world.emit('policy_error',f'国家{n}策略失败，保持原命令',error=result['error'],nation=n)
            for cmd in result['commands']:
                error=command_error(cmd)
                outcome={'ok':False,'error':error} if error else world.command(n,cmd)
                self.metrics[n]['malformed_commands']+=error is not None
                self.metrics[n]['invalid_commands']+=not outcome.get('ok',False)
                answers.append(outcome)
        return answers

    def close(self):
        for n in self.nations:self._stop(n)
