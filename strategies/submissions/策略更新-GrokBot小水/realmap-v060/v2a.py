"""v2a 纯守门：门堡320/前线250驻军+积极解围，进攻参数保持原版"""
from nk_agent import make
decide=make(dict(relief_factor=1.0,relief_eta=168),gate_goal=320,front_goal=250)
