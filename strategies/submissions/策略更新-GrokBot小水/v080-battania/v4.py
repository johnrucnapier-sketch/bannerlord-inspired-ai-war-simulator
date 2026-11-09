"""v4：回到 v1 已验证有效的开局（只打公共猎物西帝国），补上对手模型的教训。
原则：
1 开局第一时间锁定和平：对瓦兰迪亚等接壤国直接提互不侵犯（开局各国压力大、几乎都接受），瓦兰迪亚排第一；非接壤国求和。
2 互不侵犯到期前 10 天内主动续签（接壤国优先），挡住"闲下来的强邻挑最弱邻国宣战"。
3 一次只打一场仗；有第二个敌人立即对它提互不侵犯/求和。
4 西帝国灭亡后只趁火打劫：目标必须正与另一邻国交战，且城数不超过我（≤1.0 倍）；瓦兰迪亚同样适用——绝不单挑一个专心对付我的瓦兰迪亚。
5 交战对象城数超过我 1.3 倍就主动求和、也接受求和；城数 <8 时接受任何停战。
6 同盟只接受与我共打当前目标且不带来新战争的。
唯一特殊战略指导：先灭西帝国，和瓦兰迪亚、北帝国赛跑抢它的城（它被四国夹击，是公共猎物）。"""
from bat_core import make
P=dict(name='v4',directive_target=0,adj_weight=1.0,third_war_weight=1.0,panic_cities=8,
       declare_ready=.6,declare_food=10,rear_nap=True,allow_alliance=True,nap_first=True,renew_hours=240,
       sticky=True,vulture=True,max_target_ratio=1.0,exit_losing=True,exit_ratio=1.3,one_war=True,nap_all=True)
decide=make(P)
