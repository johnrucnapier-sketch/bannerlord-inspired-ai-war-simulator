"""v5a 稳攻：v1b基础上攻城余量1.5、整补到130再出，减少赔本攻城"""
from nk_agent import make
decide=make(dict(max_armies=3,army_fraction=.85,attack_margin=1.5,refit_target=130,relief_factor=1.0,relief_eta=168),gate_goal=320,front_goal=250)
