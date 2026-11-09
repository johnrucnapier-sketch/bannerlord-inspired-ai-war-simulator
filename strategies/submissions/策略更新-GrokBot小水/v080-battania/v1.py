"""v1 原则：一线作战、其余求和、后方互不侵犯、只结共同对敌且不引入新战争的同盟。
特殊战略指导：先灭西帝国(nation 0)，西帝国灭亡后自动转向最软的接壤国。"""
from bat_core import make
P=dict(name='v1',directive_target=0,adj_weight=1.0,third_war_weight=1.0,panic_cities=8,
       declare_ready=.6,declare_food=10,rear_nap=True,allow_alliance=True)
decide=make(P)
