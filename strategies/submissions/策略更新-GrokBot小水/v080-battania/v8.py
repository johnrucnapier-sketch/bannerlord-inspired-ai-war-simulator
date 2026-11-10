"""v8：遏制瓦兰迪亚（唯一特殊战略指导），融合用户 t424u 的格局判断。
唯一特殊战略指导——"遏制瓦兰迪亚"：
  a) 西帝国（≥6 城、还算健康）正与瓦兰迪亚交战、且除此外没有别的仗时，加入对瓦兰迪亚的战争；
  b) 若西帝国已被打到 ≤5 城、仍在与瓦兰迪亚交战（已救不回来），就抢在瓦兰迪亚之前拿下西帝国残余城，不让头号威胁坐大。
原则：
1 开局互不侵犯顺序：瓦兰迪亚→西帝国→北帝国→斯特吉亚，非接壤国求和；对方吃紧时提前续签，闲着的强邻（北帝国）优先。
2 一次只打一场仗；被第二国宣战（v7 里北帝国两次趁我们打瓦兰迪亚时宣战）就每个窗口对它提互不侵犯——不提停战：
  对只和我们打的健康邻国，停战需压力≈2.7，互不侵犯只需 0.7，它的野战军一被打残就会接受（v7 的 1178 次停战提议全部被拒，13 年冻结在两线战争）。
3 打不过（对方城数 > 我 1.3 倍）时同样优先提互不侵犯脱身。
4 斯特吉亚被瓜分时要分一杯羹：它正被一个"只打它"的邻国拖住、且城数 ≤ 我 1.0 倍时加入（v7 里斯特吉亚的 9 城全被库赛特拿走）。
5 北帝国受保护：除非它 ≤ 我 0.6 倍，不对它开战。
6 同盟只接受共打目标且不带新战争的。"""
from persuade import make
P=dict(name='v8',cur_must_qualify=True,directive_target=None,join_gate=(5,0),gate_ratio=1.25,gate_exclusive=False,gate_partner_min=6,contain=5,
       nap_bonus={5:30,0:20,1:10,6:10},nap_over_peace=True,
       protect_until=dict(while_alive=None,nations=[1]),
       panic_cities=8,exit_ratio=1.3,renew_hours=500,
       max_target_ratio=1.0,busy_ratio=.8,weak_ratio=.6,declare_ready=.6,declare_food=10)
decide=make(P)
