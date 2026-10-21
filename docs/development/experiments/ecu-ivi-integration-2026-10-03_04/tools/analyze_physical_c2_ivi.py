from pathlib import Path
import json,sys,collections,re,datetime
b=Path('docs/development/experiments/ecu-ivi-integration-2026-10-03_04');sys.path.insert(0,str(b/'tools'));from compare_ivi_can import read_can
v=b/'raw/PHYSICAL-PILOT-001-C2/ivi/security-pilot-on-001';e=b/'raw/PHYSICAL-PILOT-001-C2/results/physical-pilot-001-c2'
c=read_can(v/'candump.log','absolute');rr=[json.loads(x) for x in (v/'receiver.jsonl').read_text().splitlines()];rx=[x for x in rr if x.get('result')=='FRAME'];rows=[]
for p in e.glob('*.jsonl'):
 if p.name=='attempts.jsonl':continue
 for l in p.read_text().splitlines():
  a=json.loads(l)
  if 'frame' in a:rows.append((a['t'],p.stem,a))
rows.sort(key=lambda x:x[0]);assert [(a['can_id'],a['data']) for _,_,a in rows]==[(x[2],x[3]) for x in c[:len(rows)]]
filtered=[x for x in c if x[2] in [256,257,258,259,512]];assert [(x[2],x[3]) for x in filtered]==[(x['can_id'],x['data']) for x in rx]
by_index={i:x for i,x in zip([i for i,x in enumerate(c) if x[2] in [256,257,258,259,512]],rx)};stats={};events=[];times={}
for i,(_,name,a) in enumerate(rows):
 if a['own']:times.setdefault(name,[]).append(c[i][0])
 if i not in by_index:continue
 x=by_index[i];stats.setdefault(name,collections.Counter())[x.get('message')]+=1
 if any(y.get('kind')=='PUBLISHED' and y.get('own') for y in a.get('outcomes',[])):events.append(dict(can_index=i,ecu=a,ivi=x))
loads=[int(x) for x in re.findall(r'(\d+)%',(v/'canbusload.log').read_text())]
fmt=lambda t:datetime.datetime.fromtimestamp(t/1e9,datetime.timezone(datetime.timedelta(hours=9))).isoformat()
out=dict(can_frames=len(c),ecu_observed_frames=len(rows),ecu_exact_prefix=True,ivi_tail_frames=[dict(time=fmt(x[0]),can_id=x[2],data=x[3]) for x in c[len(rows):]],receiver_frames=len(rx),allowlisted_receiver_exact_sequence=True,secoc_all_on=all(x.get('secoc_on') is True for x in rx),messages=dict(collections.Counter(x.get('message') for x in rx)),by_raw_segment=stats,replay_origin_event=events,attack_first_last_ivi_time={k:[fmt(min(v)),fmt(max(v))] for k,v in times.items()},ivi_rx_delta=21416-13931,busload_display_max_percent=max(loads),busload_samples=len(loads),other_receiver_results=dict(collections.Counter(x.get('result') for x in rr if x.get('result')!='FRAME')))
(b/'analysis/physical-pilot-001-c2-crosscheck.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
