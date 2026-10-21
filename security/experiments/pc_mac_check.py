"""Local PC orchestration for existing ECU and visible IVI; no keys leave nodes."""
import argparse,json,shlex,subprocess,time,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--settings',type=Path,required=True)
parser.add_argument('--ivi-log',required=True,help='Path relative to IVI user home')
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--i-am-on-a-test-bus',action='store_true')
args=parser.parse_args()
if not args.i_am_on_a_test_bus:parser.error('isolated test bus required')
if Path(args.ivi_log).is_absolute() or '..' in Path(args.ivi_log).parts:parser.error('relative IVI log path required')
from security.experiments.score_mac_probe import score
root=Path(__file__).resolve().parents[2]
cfg=json.loads(args.settings.read_text())
run='mac-repeat-'+time.strftime('%Y%m%d-%H%M%S')
out=args.out;out.mkdir(parents=True,exist_ok=False)
ivi_path=args.ivi_log
parts=shlex.split(cfg['attacker'][-1])
if len(parts)<5 or parts[0]!='cd' or parts[2:4]!=['&&','exec']:raise ValueError('expected cd PROJECT && exec PYTHON attacker command')
project=parts[1]
python=parts[4]
if not Path(python).is_absolute():python=str(Path(project)/python)
def call(role,code,timeout=20):
    cmd=cfg[role][:-1]+['python3 -c '+shlex.quote(code)]
    return subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=timeout).stdout
# Assert the existing IVI log is actively receiving current product frames.
check="""import pathlib,time,json
p=pathlib.Path.home()/PATH
if not p.exists() or time.time()-p.stat().st_mtime>5:raise SystemExit('IVI log is missing/stale: restart logged dashboard or ECU')
with p.open('rb') as f:
 f.seek(max(0,p.stat().st_size-65536)); chunk=f.read().splitlines()
rows=[]
for line in chunk:
 try:rows.append(json.loads(line))
 except ValueError:pass
frames=[r for r in rows if r.get('result')=='FRAME' and r.get('can_id')==258 and r.get('process_result')==2 and r.get('secoc_on')]
if not any(0<=time.monotonic()-int(r['timestamp_ns'])/1e9<3 for r in frames):raise SystemExit('No fresh authenticated IVI normal publication')
print('IVI_NORMAL_READY')
""".replace('PATH',repr(ivi_path))
try:
    print(call('receiver_on',check),flush=True)
    source=(root/'security/experiments/mac_rejection_probe.py').read_text()
    remote_out='tmp/'+run
    code="import os,sys;os.chdir("+repr(project)+");sys.path.insert(0,os.getcwd());sys.argv=['mac_probe','--out',"+repr(remote_out)+",'--i-am-on-a-test-bus'];exec(compile("+repr(source)+",'mac_probe','exec'))"
    target=cfg['attacker'][:-1]+[shlex.quote(python)+' -u -c '+shlex.quote(code)]
    print('30회 변조 인증 주입 시작',flush=True)
    with (out/'probe.jsonl').open('x') as log, (out/'probe.stderr').open('x') as err:
        subprocess.run(target,stdout=log,stderr=err,check=True,timeout=130)
    probe=[json.loads(x) for x in (out/'probe.jsonl').read_text().splitlines()]
    auths=[r['auth'] for r in probe if r.get('result')=='PREPARED']
    time.sleep(1)
    fetch="import json,pathlib; wanted=set("+repr(auths)+"); p=pathlib.Path.home()/"+repr(ivi_path)+"\nwith p.open() as f:\n for line in f:\n  try:r=json.loads(line)\n  except ValueError:continue\n  if r.get('result')=='FRAME' and r.get('can_id')==258 and r.get('data') in wanted:print(json.dumps(r))"
    data=call('receiver_on',fetch)
    (out/'ivi-matches.jsonl').write_text(data)
    result=score(probe,[json.loads(x) for x in data.splitlines()])
    (out/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},ensure_ascii=False,indent=2))
except Exception as e:
    (out/'failure.txt').write_text(str(e))
    print('STOPPED:',e)
    raise
finally:
    print('PC 결과 폴더:',out,flush=True)
