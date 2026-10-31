"""Extract a verified dataset TAR.ZST without running any strategy."""
import argparse,shutil,subprocess,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=Path(a.output)
if out.exists():raise SystemExit('Use a new output directory: '+str(out))
proc=None
if shutil.which('zstd'):
 proc=subprocess.Popen(['zstd','-dc',a.archive],stdout=subprocess.PIPE);reader=proc.stdout
else:
 try:import zstandard
 except ImportError:raise SystemExit('Need zstd CLI or Python zstandard package (can install in your own Python environment).')
 reader=zstandard.ZstdDecompressor().stream_reader(open(a.archive,'rb'))
try:
 out.mkdir(parents=True)
 with tarfile.open(fileobj=reader,mode='r|') as t:t.extractall(out,filter='data')
finally:
 reader.close()
 if proc and proc.wait()!=0:raise SystemExit('zstd decompression failed')
print('Extracted',out)
