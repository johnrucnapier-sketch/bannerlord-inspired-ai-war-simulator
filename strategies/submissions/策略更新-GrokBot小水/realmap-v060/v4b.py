"""v4b 门堡轻守+常驻：前60天阿塔3/叙拉2，之后门堡各常驻1队；进攻同v1b"""
from nk_agent import make_guard
decide=make_guard(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),320,250,{'castle_EN6':3,'castle_EN8':2},60,1)
