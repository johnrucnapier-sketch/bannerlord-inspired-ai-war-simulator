"""v1b 集中进攻+守门堡+积极解围"""
from nk_agent import make
decide=make(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),gate_goal=320,front_goal=250)
