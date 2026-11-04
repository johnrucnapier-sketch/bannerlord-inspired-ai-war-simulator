"""v2b 重守门+集中：门堡420/前线300，解围0.9倍即出，3路军团"""
from nk_agent import make
decide=make(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=0.9,relief_eta=168),gate_goal=420,front_goal=300)
