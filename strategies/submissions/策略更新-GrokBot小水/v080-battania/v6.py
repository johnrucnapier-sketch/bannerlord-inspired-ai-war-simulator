"""v6 = v5 + 精确外交探针（全关系矩阵/条约到期/同盟 + 静态地图精确邻接）+ 说服层（按对手接受公式择时提议）。
原则：1 开局对接壤交战国直接提互不侵犯（它们压力大必接受），非接壤求和；2 互不侵犯在对方吃紧时提前续签，闲着的强邻优先；
3 一次只打一场仗；4 宣战目标须"被拖住"：它正和一个只跟它打的接壤国交战（城数 ≤ 我 1.25 倍），或正在别处打仗且 ≤ 我 1.0 倍，或 ≤ 我 0.6 倍；
5 预测对方会接受才提停战，打不过（对方城数 > 我 1.3 倍）时求和；6 同盟只接受共打目标且不带新战争的。
唯一特殊战略指导：先灭西帝国。"""
from persuade import make
P=dict(name='v6',directive_target=0,panic_cities=8,exit_ratio=1.3,renew_hours=500,
       max_target_ratio=1.25,busy_ratio=1.0,weak_ratio=.6,declare_ready=.6,declare_food=10)
decide=make(P)
