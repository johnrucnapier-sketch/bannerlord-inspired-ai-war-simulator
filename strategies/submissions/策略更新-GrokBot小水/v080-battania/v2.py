"""v2：在 v1 上按"读懂对手"修订。
- 一次只打一场仗：只有在没有任何战争时才宣战（修 v1 在与瓦兰迪亚交战中又对斯特吉亚宣战的漏洞）。
- 趁火打劫：西帝国灭亡后，只挑"正和另一个邻国交战"且城数不超过我 1.25 倍的接壤国；没有就按兵不动、续签互不侵犯。
- 战中锁定目标；打不过（对方城数 > 我 1.3 倍）就主动求和，也接受对方求和。
- 对所有非目标国（不只是接壤国）签互不侵犯，堵住"对手拉盟友同步宣战"。
特殊战略指导：仍是先灭西帝国。"""
from bat_core import make
P=dict(name='v2',directive_target=0,adj_weight=1.0,third_war_weight=1.0,panic_cities=8,
       declare_ready=.7,declare_food=14,rear_nap=True,allow_alliance=True,
       sticky=True,vulture=True,max_target_ratio=1.25,exit_losing=True,exit_ratio=1.3,one_war=True,nap_all=True)
decide=make(P)
