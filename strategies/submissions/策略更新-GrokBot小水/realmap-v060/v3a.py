"""v3a 开局门堡集结：前60天阿塔科尼亚堡、墨卡罗维亚堡、瓦拉戈斯堡各3队、叙拉托斯堡2队，其余同v1b"""
from nk_agent import make_guard
decide=make_guard(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),320,250,{'castle_EN6':3,'castle_EN9':3,'castle_EN1':3,'castle_EN8':2},60)
