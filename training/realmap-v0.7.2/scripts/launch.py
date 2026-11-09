"""Launch the private Python server and Godot; shut our server down on exit."""
import os
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path
from websockets.sync.client import connect

root=Path(__file__).resolve().parent.parent

def main():
    if sys.platform=='win32':
        candidates=list((root/'.tools').glob('Godot*_win64.exe'))
    elif sys.platform=='darwin':
        candidates=[root/'.tools/Godot.app/Contents/MacOS/Godot']
    else:
        candidates=sorted((root/'.tools').glob('Godot*_linux.*'))
    candidates=[p for p in candidates if p.is_file()]
    installed=shutil.which('godot') or shutil.which('godot4')
    if not candidates and installed:
        candidates=[Path(installed)]
    if not candidates or not candidates[0].exists():
        raise SystemExit('Godot runtime not found under .tools or on PATH')
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',18765))==0:
            raise SystemExit('Port 18765 is occupied. Close the earlier simulator session first.')
    (root/'artifacts').mkdir(exist_ok=True)
    with (root/'artifacts/server.log').open('w',encoding='utf-8') as log:
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        server=subprocess.Popen([sys.executable,'-m','aiwar.server'],cwd=root,stdout=log,stderr=log,creationflags=flags)
        try:
            for _ in range(100):
                if server.poll() is not None: raise RuntimeError('Core failed; see artifacts/server.log')
                try:
                    with connect('ws://127.0.0.1:18765',open_timeout=0.3):
                        break
                except (OSError,TimeoutError):
                    time.sleep(.1)
            else:
                raise RuntimeError('Core did not become ready; see artifacts/server.log')
            with (root/'artifacts/viewer.log').open('w',encoding='utf-8') as viewer_log:
                subprocess.run([str(candidates[0]),'--path',str(root/'godot')]+(['--']+sys.argv[1:] if len(sys.argv)>1 else []),cwd=root,stdout=viewer_log,stderr=viewer_log,check=True)
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
