"""Rebuild a saved world's command journal and verify its exact final state."""
import argparse
from .engine import World

def replay(path):
    expected=World.load(path)
    world=World(expected.seed,expected.cfg)
    index=0
    while world.hour<expected.hour:
        while index<len(expected.commands) and expected.commands[index]['hour']==world.hour:
            item=expected.commands[index]
            world.command(item['nation'],item['command'])
            index+=1
        world.step()
    while index<len(expected.commands) and expected.commands[index]['hour']==world.hour:
        item=expected.commands[index];world.command(item['nation'],item['command']);index+=1
    if world.physics_digest()!=expected.physics_digest():
        raise RuntimeError('Replay differs from saved state')
    return world

def main():
    p=argparse.ArgumentParser();p.add_argument('save');a=p.parse_args()
    w=replay(a.save);print('REPLAY_OK',w.hour,w.digest())

if __name__=='__main__':main()
