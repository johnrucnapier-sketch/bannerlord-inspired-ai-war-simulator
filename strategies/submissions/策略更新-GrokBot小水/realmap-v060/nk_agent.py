"""北帝国 realmap v0.6.0 策略框架（GrokBot小水）。基于自带原版风味基准的独立副本，按版本开关改动。"""
from nk_log import LogisticsPlanner
from nk_base import PARAMETERS
GATES={'castle_EN6','castle_EN8'}  # 阿塔科尼亚堡、叙拉托斯堡
def make(overrides=None,gate_goal=None,front_goal=None):
    class North(LogisticsPlanner):
        P=dict(PARAMETERS,**(overrides or {}))
        def troop_goal(self,d):
            dep=self.depth.get(d['id'],999)
            if gate_goal and d['id'] in GATES:return gate_goal
            if front_goal and dep==0:return front_goal
            return 200 if dep<=1 else 100
    def decide(obs,style=None):
        if obs.get('mode')!='realmap':return []
        return North(obs).run()
    return decide

from nk_base import distance
def make_guard(overrides=None,gate_goal=None,front_goal=None,guard=None,opening_days=60,late_guard=0):
    """guard: {城堡ID: 开局驻守领主队数}。驻在城下1000内的部队会自动参加守城。"""
    base=make(overrides,gate_goal,front_goal)
    def decide(obs,style=None):
        cmds=base(obs)
        if obs.get('mode')!='realmap':return cmds
        n=obs['nation'];hour=obs['hour']
        per=guard if hour<opening_days*24 else ({k:late_guard for k in guard} if late_guard else {})
        if not per:return cmds
        cities={c['id']:c for c in obs['cities']}
        parties=sorted((u for u in obs['units'] if u['nation']==n and u['kind']=='party' and not u['army'] and not u['battle']),key=lambda u:u['id'])
        used=set();extra=[]
        for gid,k in sorted(per.items()):
            g=cities.get(gid)
            if not g or g['nation']!=n:continue
            # 已在岗者优先（订单带guard标记），其余按距离
            cand=sorted(parties,key=lambda u:((u.get('order') or {}).get('guard')!=gid,distance(u,g),u['id']))
            for u in [u for u in cand if u['id'] not in used][:k]:
                used.add(u['id'])
                o=u.get('order') or {}
                if distance(u,g)>300 or o.get('guard')!=gid:
                    extra.append(dict(type='move',unit=u['id'],x=g['x'],y=g['y'],guard=gid))
        cmds=[c for c in cmds if c.get('unit') not in used or c['type'] in('set_strength','set_composition')]
        return (extra+cmds)[:100]
    return decide

def make_phased(phases,gate_goal=None,front_goal=None):
    """phases: [(起始日, 参数覆盖)]，按当前日取最后一个起始日<=今天的参数组。"""
    makers=[(day,make(ov,gate_goal,front_goal)) for day,ov in sorted(phases,key=lambda p:p[0])]
    def decide(obs,style=None):
        today=obs['hour']/24;fn=makers[0][1]
        for day,f in makers:
            if today>=day:fn=f
        return fn(obs)
    return decide
