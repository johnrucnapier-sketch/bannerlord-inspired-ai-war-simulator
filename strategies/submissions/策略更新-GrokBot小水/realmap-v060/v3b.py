"""v3b 开局门堡集结+常驻：前60天门堡各3队，之后各常驻2队（含叙拉托斯堡）"""
from nk_agent import make_guard
decide=make_guard(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),320,250,{'castle_EN6':3,'castle_EN9':3,'castle_EN1':3,'castle_EN8':2},60,2)
