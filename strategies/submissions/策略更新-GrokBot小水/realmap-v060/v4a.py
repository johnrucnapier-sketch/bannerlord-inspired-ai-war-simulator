"""v4a 只轻守门堡：前60天阿塔科尼亚堡3队、叙拉托斯堡2队，进攻参数同v1b（不再拴墨卡/瓦拉）"""
from nk_agent import make_guard
decide=make_guard(dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168),320,250,{'castle_EN6':3,'castle_EN8':2},60)
