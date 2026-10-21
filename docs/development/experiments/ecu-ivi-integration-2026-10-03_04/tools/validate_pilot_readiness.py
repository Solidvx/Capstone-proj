from pathlib import Path
import json,random,hmac,hashlib,struct
from dataclasses import replace
from security.experiments.measure_runtime_fpr import generate_normal
from security.experiments.evaluate_normal import evaluate
from security.ids.runtime import train_model
root=Path('tmp/pilot-readiness-v2');root.mkdir(exist_ok=True)
key=bytes(range(32)) # explicit synthetic dummy, not device key
captures={}
for name,seed in [('fit',9001),('calibration',9002),('eval1',9003),('eval2',9004),('eval3',9005)]:
 frames=generate_normal(300,random.Random(seed));payload=None;out=[]
 for f in frames:
  if f.can_id==256:payload=f.data
  else:f=replace(f,data=hmac.new(key,struct.pack('>HI',256,int.from_bytes(f.data[4:],'big'))+payload,hashlib.sha256).digest()[:4]+f.data[4:])
  out.append(f)
 path=root/(name+'.jsonl');path.write_text(''.join(json.dumps({'t':f.t,'can_id':f.can_id,'data':f.data.hex()})+'\n' for f in out)+json.dumps({'tick':300})+'\n')
 captures[name]=(path,out)
model=train_model(captures['fit'][0],captures['calibration'][0]);report={'environment':'synthetic','seeds':{'fit':9001,'calibration':9002,'evaluations':[9003,9004,9005]},'duration_each_s':300,'calibration':model.calibration,'results':{}}
for name in ['eval1','eval2','eval3']:
 r=evaluate(captures[name][1],300,model=model,key=key);report['results'][name]={k:v for k,v in r.items() if k!='windows'}
report['input_sha256']={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,(p,f) in captures.items()}
(root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
