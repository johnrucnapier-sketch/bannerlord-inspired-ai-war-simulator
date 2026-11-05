"""v5b 双军团重拳：v1b基础上军团上限2路（兵力更集中），出征比例0.85、余量1.3"""
from nk_agent import make
decide=make(dict(max_armies=2,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),gate_goal=320,front_goal=250)
