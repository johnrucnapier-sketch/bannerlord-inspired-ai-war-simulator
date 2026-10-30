"""Grok Bot v21b-hunt (made by GrokBot 小水): v20 + 协同清剿 (coordinated patrol hunting), no feint.
Shared code lives in ../v21a-feint/agent.py; this wrapper only flips the defaults GB_FEINT=0, GB_HUNT=1
(any GB_* already in the environment still wins)."""
import os, runpy
os.environ.setdefault('GB_FEINT', '0'); os.environ.setdefault('GB_HUNT', '1')
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v21a-feint', 'agent.py'), run_name='__main__')
