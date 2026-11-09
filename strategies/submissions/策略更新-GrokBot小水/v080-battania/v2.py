"""v2：核心是"把巴丹尼亚打造成无后顾之忧的边疆国"。
原则（外交与战略）：
1 一次只打一场仗：没有任何战争时才宣战；对其余交战国全部求和，对非目标国签互不侵犯（不只接壤国，堵住对手拉盟友同步宣战）。
2 战中锁定目标；打不过（对方城数 > 我 1.3 倍）就主动求和，也接受它的求和；城数 <8 时接受任何停战。
3 目标清单完成后才趁火打劫：只挑正在和别的邻国交战、城数不超过我 1.25 倍的接壤国。
4 同盟只接受与我共同打当前目标、且不带来新战争的。
唯一特殊战略指导：先灭瓦兰迪亚，坐稳西海岸当后方——趁它还和西帝国交战时动手；西部（瓦兰迪亚→西帝国）清完之前不对东方开战。"""
from bat_core import make
P=dict(name='v2',directive_target=None,directive_order=[5,0],adj_weight=1.0,third_war_weight=1.0,panic_cities=8,
       declare_ready=.6,declare_food=10,rear_nap=True,allow_alliance=True,
       sticky=True,vulture=True,max_target_ratio=1.25,exit_losing=True,exit_ratio=1.3,one_war=True,nap_all=True)
decide=make(P)
