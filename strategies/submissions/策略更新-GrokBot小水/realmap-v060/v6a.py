"""v6a 终局冲刺：v1b参数；第760天起4路军团、出征0.95、余量1.15抢城；最后8天不再新开出征（只解围）"""
from nk_agent import make_phased
B=dict(max_armies=3,army_fraction=.85,attack_margin=1.3,relief_factor=1.0,relief_eta=168)
decide=make_phased([(0,B),(760,dict(B,max_armies=4,army_fraction=.95,attack_margin=1.15)),(832,dict(B,max_armies=0))],320,250)
