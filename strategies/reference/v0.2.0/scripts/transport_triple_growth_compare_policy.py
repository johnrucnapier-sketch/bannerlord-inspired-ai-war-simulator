"""Identical resource growth, always timed escort versus always triple P5."""
from scripts.transport_growth_policy import GrowthController, distance, LegacyController

class Controller(GrowthController):
    def __init__(self,target=57,floor=18,style='timed57'):
        assert style in ('timed57','p557')
        super().__init__(target,floor,'grow57')
        self.mode=style
    def escort_order(self,obs,u,c,v,own,bandits,ready,commands,move):
        if self.mode=='timed57':
            old=self.style
            try:
                self.style='timed'
                return LegacyController.escort_order(self,obs,u,c,v,own,bandits,ready,commands,move)
            finally:self.style=old
        uid=u['id']
        eligible=[b for b in bandits if min(ready,key=lambda pair:(distance(pair[0],b),pair[0]['id']))[0]['id']==uid]
        current=next((b for b in eligible if b['id']==(u.get('order') or {}).get('target')),None)
        if current and distance(u,current)<10000 and distance(current,v)<18000:return
        nearby=[b for b in eligible if distance(u,b)<8000]
        if nearby:
            b=min(nearby,key=lambda b:(distance(u,b),b['id']))
            commands.append(dict(type='attack',unit=uid,target=b['id']));return
        if u.get('path') and (u.get('order') or {}).get('strength_route'):return
        points=[v,c];index=self.route_index.get(uid,-1)
        for _ in points:
            index=(index+1)%len(points)
            if distance(u,points[index])>500:break
        self.route_index[uid]=index
        move(u,points[index],strength_route=True)
