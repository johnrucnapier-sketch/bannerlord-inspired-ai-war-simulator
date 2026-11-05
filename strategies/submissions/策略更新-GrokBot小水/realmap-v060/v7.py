"""v7 稳攻重拳：v5a(余量1.5、整补130)+v5b(军团上限2路)合并，门堡320/前线250，积极解围"""
from nk_agent import make
decide=make(dict(max_armies=2,army_fraction=.85,attack_margin=1.5,refit_target=130,relief_factor=1.0,relief_eta=168),gate_goal=320,front_goal=250)
