"""Grok Bot v21c-combo (made by GrokBot 小水): v20 + 协同清剿 (hunting, as v21b) + 声东击西 (feint, as tuned v21a2).
Shared code lives in ../v21a2-feint/agent.py; this wrapper only sets the defaults GB_FEINT=1, GB_HUNT=1
(any GB_* already in the environment still wins)."""
import os, runpy
os.environ.setdefault('GB_FEINT', '1'); os.environ.setdefault('GB_HUNT', '1')
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v21a2-feint', 'agent.py'), run_name='__main__')
