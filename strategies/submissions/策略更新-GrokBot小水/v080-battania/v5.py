"""v5：保留 v4 的安全开局，加上真正的扩张引擎。
v4 教训：开局锁和平（含瓦兰迪亚）+只打西帝国很稳，13→17城后9年无人来犯；但"对方正在别处打仗"的判断
有漏洞——外国据点在观察里没有 neighbors 字段，distracted() 永远为空，所以趁火打劫从没触发过（v2/v3 的同类门槛也一直无效）。
现改用公开的 supply_neighbors 推断外国邻接。
原则：
1 开局第一时间对接壤国直接提互不侵犯（瓦兰迪亚优先），非接壤国求和；互不侵犯到期前续签。
2 一次只打一场仗；出现第二个敌人立即对它提互不侵犯/求和。
3 扩张引擎（西帝国不再接壤后）：在接壤国里挑目标——正与别国交战且城数 ≤ 我 1.25 倍（瓦兰迪亚忙于和西帝国打仗时可以趁机打），
  或城数 ≤ 我 0.6 倍（以强凌弱）；按"城少、接壤多、仗多"排序；整备 ≥0.6、粮 ≥10 天才宣战。
4 交战对象城数超过我 1.3 倍就主动求和、也接受求和；城数 <8 时接受任何停战。
5 同盟只接受与我共打当前目标且不带来新战争的。
唯一特殊战略指导：先灭西帝国（四国夹击的公共猎物，和邻居抢它的城）。"""
from bat_core import make
P=dict(name='v5',directive_target=0,adj_weight=1.0,third_war_weight=1.0,panic_cities=8,
       declare_ready=.6,declare_food=10,rear_nap=True,allow_alliance=True,nap_first=True,renew_hours=240,
       sticky=True,vulture=True,max_target_ratio=1.25,weak_ratio=.6,exit_losing=True,exit_ratio=1.3,one_war=True,nap_all=True)
decide=make(P)
