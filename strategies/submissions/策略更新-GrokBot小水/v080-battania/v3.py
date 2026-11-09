"""v3 分阶段战略（融合"边疆国"洞见和用户三阶段方案）。见 reports/15-v080-巴丹尼亚外交.md。
唯一特殊战略指导：先灭瓦兰迪亚，但只在它同时与别国（西帝国）交战时进攻；否则防守、只守不攻。"""
from phased import make
P=dict(name='v3',panic_cities=7,nap_first=True,p1_seek_peace=True,declare_ready=.6,declare_food=10,renew_hours=240,
       p2_ratio=.8,p3_cities=34,p3_lead=1.3,p3_ratio=.8,p3_min_victim=6)
decide=make(P)
