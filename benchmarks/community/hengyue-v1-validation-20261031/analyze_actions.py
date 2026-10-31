#!/usr/bin/env python3
"""Summarize existing formal JSONL gzip logs; never execute an agent or simulation.

Usage: python analyze_actions.py BATCH [BATCH ...] --output actions.json
Outputs only relative evidence locations, safe game fields, and registered hashes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re

ACTION_TYPES = ('attack', 'raid', 'siege')
UNIT_KEYS = ('id','kind','nation','x','y','healthy','wounded','food','hungry','battle','army')
COMMAND_KEYS = ('type','unit','target','city','destination','count','food','x','y','relief_action','relief_city')
BATTLE_KEYS = ('id','kind','start','city','relief_for','relief_battle','x','y','prepare_hours','paused_hours')


def clean(value):
    if isinstance(value, str):
        value = re.sub(r'(?:/Users/|/private/|/tmp/|/home/|/mnt/|/opt/|/Volumes/)[^\s\"\']+', '[local-path]', value)
        value = re.sub(r'[A-Za-z]:[\\/][^\s\"\']+', '[local-path]', value)
        return value[:500]
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, list): return [clean(v) for v in value]
    return value


def pick(obj, keys): return {k:obj[k] for k in keys if k in obj}


def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): return None


def evidence(label, job, nation, line, record, observation):
    terminal = record.get('type') == 'terminal'
    return {'log':f'{label}/{job}/nation-{nation}.jsonl.gz', 'line_1based':line,
            'hour':observation.get('hour'), 'request_id':record.get('request',{}).get('request_id'),
            'observation_pointer':'/observation' if terminal else '/request/observation',
            'record_type':'terminal' if terminal else 'decision'}


def scan_game(batch, label, job, summary, max_examples):
    side = summary.get('side')
    row = {'batch':label,'job_id':job,'seed':summary.get('seed'),'side':side,
           'status':summary.get('status','unknown'), 'planned_days':summary.get('days')}
    if side not in ('blue','red'):
        row['scan_status']='invalid_summary_side'; return row
    nation=0 if side=='blue' else 1
    row['nation']=nation
    result=summary.get('result') or {}
    row['result']=pick(result,('winner','reason','cities','hour'))
    row['outcome']=('draw' if result.get('winner') is None else 'win' if result['winner']==nation else 'loss') if result else 'unknown'
    row['final_hour']=result.get('hour')
    row['source_sha256']={k:v for k,v in (summary.get('source_sha256') or {}).items()
                          if k in ('agent','opponent','freeze/v0.2.0.json')}
    row['config_sha256']=summary.get('config_sha256')
    row['own_log_registered_sha256']=(summary.get('raw_log_sha256') or {}).get(f'nation-{nation}.jsonl.gz')
    row['recorded_own_faults']={k:(summary[k][nation] if isinstance(summary.get(k),list) and len(summary[k])>nation else None)
       for k in ('agent_errors','command_rejections','timeouts','stderr_tracebacks','stderr_policy_exceptions')}
    if row['status']!='completed':
        row['scan_status']='not_completed_not_scanned'; return row
    trace=batch/job/f'nation-{nation}.jsonl.gz'
    if not trace.exists():
        row['scan_status']='missing_own_log'; return row
    all_commands=Counter(); actions=defaultdict(lambda:defaultdict(Counter)); target_ids=defaultdict(set)
    invalid=Counter(); invalid_by_type=Counter(); agent_errors=Counter()
    food=Counter(); hunger=Counter(); zero_ids=set(); hungry_ids=set(); seen_relief={}; relief_roles=Counter()
    examples=defaultdict(list); parent_city={}; own_sieges=set(); previous_ownership=None
    action_example_keys=set(); rejected_example_counts=Counter(); decision_count=0; terminal_count=0
    scanned=0; last_hour=None; alignment_mismatches=0; battle_counts=Counter(); observed_battles=set()
    def add(key,item):
        if len(examples[key])<max_examples: examples[key].append(item)
    try:
        with gzip.open(trace,'rt',encoding='utf-8') as handle:
            for line,text in enumerate(handle,1):
                record=json.loads(text)
                terminal=record.get('type')=='terminal'
                obs=record.get('observation') if terminal else record.get('request',{}).get('observation')
                if not isinstance(obs,dict): raise ValueError('missing observation')
                if obs.get('nation')!=nation: raise ValueError('wrong observation nation')
                scanned+=1; last_hour=obs.get('hour'); decision_count+=not terminal; terminal_count+=terminal
                loc=evidence(label,job,nation,line,record,obs)
                units={u['id']:u for u in obs.get('units',[])}
                cities={c['id']:c for c in obs.get('cities',[])}
                villages={v['id']:v for v in obs.get('villages',[])}
                own=[u for u in units.values() if u.get('nation')==nation]
                own_parties=[u for u in own if u.get('kind')=='party' and u.get('healthy',0)+u.get('wounded',0)>0]
                current_owned={c['id'] for c in cities.values() if c.get('nation')==nation and not c.get('stale',False)
                               and c.get('garrison') in units and units[c['garrison']].get('nation')==nation}
                if previous_ownership is not None and current_owned!=previous_ownership:
                    add('ownership_changes',{**loc,'lost':sorted(previous_ownership-current_owned),'gained':sorted(current_owned-previous_ownership)})
                previous_ownership=current_owned
                if not terminal:
                    food['party_observations_total']+=len(own_parties)
                    zero=[u for u in own_parties if u.get('food')==0]
                    hungry=[u for u in own if u.get('hungry') is True and u.get('healthy',0)+u.get('wounded',0)>0]
                    food['party_zero_food_observations']+=len(zero)
                    food['decisions_with_any_party_zero_food']+=bool(zero)
                    food['decisions_with_any_hungry_unit']+=bool(hungry)
                    zero_ids.update(u['id'] for u in zero); hungry_ids.update(u['id'] for u in hungry)
                    hunger.update(u.get('kind','unknown') for u in hungry)
                    if zero: add('party_zero_food',{**loc,'units':[pick(u,UNIT_KEYS) for u in zero[:max_examples]],'matching_units':len(zero)})
                    if hungry: add('hungry_units',{**loc,'units':[pick(u,UNIT_KEYS) for u in hungry[:max_examples]],'matching_units':len(hungry)})
                alerts=obs.get('relief_requests',[])
                for alert in alerts:
                    own_sieges.add(alert['battle']);parent_city[alert['battle']]=alert['city']
                for battle in obs.get('battles',[]):
                    bid=battle['id']
                    if battle.get('city'):parent_city[bid]=battle['city']
                    if bid not in observed_battles:
                        observed_battles.add(bid);battle_counts[battle.get('kind','unknown')]+=1
                    if battle.get('kind')!='relief_field':continue
                    parent=battle.get('relief_for'); cid=parent_city.get(parent)
                    involved=[u for u in own if u.get('battle')==bid]
                    role='own_city_defense' if parent in own_sieges else 'own_besieging_force' if involved and cid and cities.get(cid,{}).get('nation')!=nation else 'visible_role_unknown'
                    if bid not in seen_relief:
                        seen_relief[bid]={'role':role,'own_participants_seen':bool(involved)};relief_roles[role]+=1
                        add('observed_relief_starts',{**loc,'battle':pick(battle,BATTLE_KEYS),'city':cid,'role':role,
                            'own_participants':[pick(u,UNIT_KEYS) for u in involved[:max_examples]],'own_participant_count':len(involved),
                            'first_seen_not_necessarily_same_hour_as_start':battle.get('start')!=obs.get('hour')})
                    elif involved:seen_relief[bid]['own_participants_seen']=True
                commands=record.get('commands',[]);outcomes=record.get('outcomes',[])
                if len(commands)!=len(outcomes):alignment_mismatches+=1
                err=record.get('agent_error')
                if err:agent_errors[clean(str(err))]+=1;add('agent_errors',{**loc,'agent_error':clean(str(err))})
                for index,command in enumerate(commands):
                    kind=command.get('type','unknown');all_commands[kind]+=1
                    outcome=outcomes[index] if index<len(outcomes) else {}
                    status='accepted' if outcome.get('ok') is True else 'rejected' if outcome.get('ok') is False else 'unknown_outcome'
                    target=command.get('target'); target_obj=units.get(target) or villages.get(target) or cities.get(target)
                    target_kind=units[target].get('kind','unknown') if target in units else 'village' if target in villages else 'city' if target in cities else 'unknown_not_in_observation'
                    cmd_evidence={**loc,'command_index_0based':index,'command':pick(command,COMMAND_KEYS),
                                  'outcome':pick(outcome,('ok','error','unit'))}
                    if kind in ACTION_TYPES:
                        actions[kind][target_kind]['issued']+=1;actions[kind][target_kind][status]+=1;target_ids[(kind,target_kind)].add(target)
                        key=(kind,target_kind,status)
                        if key not in action_example_keys:
                            action_example_keys.add(key)
                            add('action_targets',{**cmd_evidence,'target_kind':target_kind,
                                'actor':pick(units.get(command.get('unit'),{}),UNIT_KEYS),
                                'observed_target':pick(target_obj or {},UNIT_KEYS+('city','population','disabled_until','stale','seen','militia_healthy'))})
                    if status=='rejected':
                        reason=clean(str(outcome.get('error','unspecified')));invalid[reason]+=1;invalid_by_type[kind]+=1
                        if rejected_example_counts[reason]<max_examples:
                            rejected_example_counts[reason]+=1;examples['rejected_commands'].append(cmd_evidence)
        row['scan_status']='complete' if terminal_count else 'no_terminal_record'
    except (OSError,EOFError,ValueError,UnicodeError) as exc:
        row['scan_status']='unreadable_or_incomplete_log'
        row['scan_error']=type(exc).__name__
    row.update(records=scanned,decision_observations=decision_count,terminal_observations=terminal_count,last_observed_hour=last_hour,
               command_counts=dict(all_commands),command_outcome_alignment_mismatches=alignment_mismatches,
               actions_by_target_kind={k:{target:{**dict(count),'distinct_target_ids':len(target_ids[(k,target)])} for target,count in v.items()} for k,v in actions.items()},
               invalid_command_reasons=dict(invalid),invalid_commands_by_type=dict(invalid_by_type),agent_error_observations=dict(agent_errors),
               food_observation_counts={**dict(food),'distinct_zero_food_party_ids':len(zero_ids),'distinct_hungry_unit_ids':len(hungry_ids)},
               hungry_unit_observations_by_kind=dict(hunger),observed_unique_battles_by_kind=dict(battle_counts),
               observed_relief_fields={'unique_battle_ids':len(seen_relief),'by_role':dict(relief_roles),'with_own_participants_seen':sum(x['own_participants_seen'] for x in seen_relief.values())},
               evidence=dict(examples))
    row['reported_rejections_match_scan']=row['recorded_own_faults']['command_rejections']==sum(invalid.values())
    return clean(row)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('batches',nargs='+',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--slow-wins',type=int,default=3,help='Longest completed full-length wins selected across input batches')
    p.add_argument('--examples',type=int,default=4,help='Maximum examples per ordinary evidence category/rejection reason')
    args=p.parse_args()
    if args.examples<1 or args.slow_wins<0:p.error('invalid evidence/candidate limit')
    labels=[x.name for x in args.batches]
    if len(set(labels))!=len(labels):p.error('batch directory basenames must be distinct')
    rows=[];batch_info=[]
    for batch,label in zip(args.batches,labels):
        manifest=read_json(batch/'experiment.json') or {}
        planned={j['job_id']:j for j in manifest.get('planned_jobs',[]) if isinstance(j,dict) and 'job_id' in j}
        jobs=set(planned)|{f.parent.name for f in batch.glob('*/summary.json')}
        if not jobs and not batch.is_dir():batch_info.append({'batch':label,'status':'missing_directory'});continue
        for job in sorted(jobs):
            summary=read_json(batch/job/'summary.json')
            if summary is None:
                rows.append({'batch':label,'job_id':job,'seed':planned.get(job,{}).get('seed'),'side':planned.get(job,{}).get('side'),
                             'status':'pending_or_unreadable_summary','scan_status':'not_scanned'});continue
            rows.append(scan_game(batch,label,job,summary,args.examples))
        batch_info.append({'batch':label,'planned_jobs':len(planned),'discovered_jobs':len(jobs)})
    full=[r for r in rows if r.get('scan_status')=='complete' and (r.get('planned_days') or 0)>=1680]
    losses=[r for r in full if r.get('outcome')=='loss']
    slow=sorted([r for r in full if r.get('outcome')=='win'],key=lambda r:r.get('final_hour') or 0,reverse=True)[:args.slow_wins]
    candidates=[{'batch':r['batch'],'job_id':r['job_id'],'reason':'loss' if r in losses else 'longest_full_length_win',
                 'outcome':r['outcome'],'final_hour':r['final_hour'],'evidence_reference':f"rows[batch={r['batch']},job_id={r['job_id']}].evidence"} for r in losses+slow]
    total_actions=defaultdict(Counter);total_invalid=Counter();total_food=Counter();total_hunger=Counter();total_relief=Counter()
    complete=[r for r in rows if r.get('scan_status')=='complete']
    for r in complete:
        for kind,targets in r['actions_by_target_kind'].items():
            for target,counts in targets.items():total_actions[kind][target]+=counts['issued']
        total_invalid.update(r['invalid_command_reasons']);total_food.update(r['food_observation_counts']);total_hunger.update(r['hungry_unit_observations_by_kind'])
        total_relief.update(r['observed_relief_fields']['by_role'])
    report={'schema':'hengyue-actions-v1','notes':[
       'Read-only post-hoc analysis; no agent/simulator execution and no strategy changes.',
       'Nation is selected exclusively from summary.side: blue=0, red=1. Counts concern the candidate only.',
       'Attack/raid/siege counts are issued command occurrences, grouped by target kind in that exact observation; accepted commands do not prove successful attacks, completed raids or captures.',
       'Zero-food and hungry counts are unit-by-decision-observation counts, excluding terminal rows; repeated observations are not independent hunger events, deaths, or durations. Garrison/militia food=0 is not counted as party food=0.',
       'Relief fields are distinct relief_field battle IDs actually visible in own observations, not inferred from orders. Starts use the observed battle.start; six-hour sampling can miss short or invisible battles, so counts are observed lower bounds.',
       'Evidence log line numbers are one-based in the decompressed JSONL; command indices are zero-based. Only relative batch/job identifiers and selected observation fields are emitted.',
       'Only completed full-length (planned days >=1680) games are selected as loss/slow-win analysis candidates. Pending logs are not scanned; malformed/truncated completed logs are marked and excluded from aggregates.',
       'Per-game distinct unit counts summed across games are game-unit pairs, not globally distinct soldiers/units.'
       ],'batches':batch_info,'coverage':{'games_listed':len(rows),'complete_logs':len(complete),'scan_statuses':dict(Counter(r['scan_status'] for r in rows))},
       'aggregate_complete_logs':{'issued_actions_by_target_kind':{k:dict(v) for k,v in total_actions.items()},'invalid_command_reasons':dict(total_invalid),
                                 'food_observation_counts':dict(total_food),'hungry_unit_observations_by_kind':dict(total_hunger),'observed_relief_fields_by_role':dict(total_relief)},
       'analysis_candidates':candidates,'rows':rows}
    text=json.dumps(clean(report),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')
    return 0

if __name__=='__main__':raise SystemExit(main())
