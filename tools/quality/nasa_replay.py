"""Compare offline NASA reconstruction candidates and actual product CSV loading.

Historical B0028 cycle3, first3600s, 0.1s grid. Linear and previous-sample
models are both reported; neither becomes a deployed policy or SOC truth.
"""
import argparse
from bisect import bisect_right
import csv
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

from .nasa_data import inspect_archive,inspect_cycle,PIN

ROOT=Path(__file__).resolve().parents[2]
FIELDS=('time_s','cell_voltage_v','current_a','temperature_c')
PROFILE=('voltage_v','current_a','temperature_c')
SOURCES=('tools/quality/nasa_replay.py','tools/quality/nasa_data.py','common/profile_loader_fixture.cpp',
    'adaptive_ecu/src/app/sensor_simulator.cpp','adaptive_ecu/include/sensor_simulator.h','adaptive_ecu/CMakeLists.txt')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Reconstruction:
    def __init__(self,data,mode):
        if mode not in ('linear','previous'):raise ValueError('explicit reconstruction candidate required')
        self.report,self.values=inspect_cycle(data);self.mode=mode;self.times=self.values['Time']

    def point(self,key,t):
        if not math.isfinite(t) or not self.times[0]<=t<=self.times[-1]:raise ValueError('no extrapolation')
        values=self.values[key];index=bisect_right(self.times,t)-1
        if index==len(values)-1 or self.mode=='previous':return values[index]
        fraction=(t-self.times[index])/(self.times[index+1]-self.times[index])
        return values[index]+fraction*(values[index+1]-values[index])

    def integral(self,start,end):
        if not self.times[0]<=start<end<=self.times[-1]:raise ValueError('invalid integral boundary')
        cursor=start;index=bisect_right(self.times,start)-1;pieces=[]
        while cursor<end:
            stop=min(end,self.times[index+1])
            left=self.point('Current_measured',cursor)
            # At a discontinuity the previous-sample model uses the left
            # segment's current through its endpoint, never the next value.
            current=left if self.mode=='previous' else (left+self.point('Current_measured',stop))/2
            pieces.append((stop-cursor)*current);cursor=stop;index+=1
        return math.fsum(pieces)


def resample(data,mode,samples=36000):
    if type(samples) is not int or not 1<=samples<=36000:raise ValueError('bounded integer sample count required')
    model=Reconstruction(data,mode)
    if model.times[0]!=0 or model.times[-1]<samples/10:raise ValueError('full t0..end raw coverage required')
    rows=[]
    for k in range(1,samples+1):
        start=(k-1)/10;end=k/10
        rows.append((end,model.point('Voltage_measured',end),model.integral(start,end)/.1,
                     model.point('Temperature_measured',end)))
    reference=model.integral(0,samples/10)/3600
    charge=math.fsum(row[2]*.1 for row in rows)/3600
    endpoint=math.fsum(model.point('Current_measured',k/10)*.1 for k in range(1,samples+1))/3600
    return rows,{'mode':mode,'samples':samples,'start_s':0,'end_s':samples/10,'grid_s':.1,
        'current':'interval average of declared reconstruction','voltage_temperature':'interval endpoint of declared reconstruction',
        'offline_reconstruction':True,'uses_future_endpoint_for_linear':mode=='linear',
        'reference_reconstruction_charge_ah':reference,'resampled_charge_ah':charge,
        'absolute_conservation_error_ah':abs(charge-reference),
        'endpoint_current_sample_charge_ah':endpoint,'endpoint_current_error_ah':endpoint-reference,
        'raw_samples':len(model.times),'raw_gap_min_s':model.report['min_gap_s'],
        'raw_gap_max_s':model.report['max_gap_s'],'operational_gap_limit_adopted':None,
        'not_claimed':['physical current between raw samples','10Hz measured sensor data','independent SOC truth','pack EKF validity']}


def float32(value):return struct.unpack('f',struct.pack('f',value))[0]


def temperature(value):
    value=float32(value)
    rounded=math.floor(value+.5) if value>=0 else math.ceil(value-.5)
    return min(70,max(-10,rounded))


def score_loaded(rows,loaded):
    if not rows or len(rows)!=len(loaded) or any(set(row)!=set(PROFILE) for row in loaded):raise ValueError('loader shape/count mismatch')
    errors=[];clamped=0;charge=[];max_voltage_error=max_current_error=0.
    for raw,observed in zip(rows,loaded):
        _,v,i,t=raw
        actual=[float(observed[key]) for key in PROFILE]
        expected=[float32(v),float32(i),temperature(t)]
        if not all(math.isfinite(value) for value in actual) or actual!=expected:
            raise ValueError('actual product loader differs from declared conversions')
        errors.append(abs(actual[2]-t));clamped+=int(float32(t)<-10 or float32(t)>70)
        max_voltage_error=max(max_voltage_error,abs(actual[0]-v));max_current_error=max(max_current_error,abs(actual[1]-i))
        charge.append(actual[1]*.1)
    return {'rows_verified':len(rows),'temperature_changed_rows':sum(e!=0 for e in errors),
        'temperature_max_abs_error_c':max(errors),'temperature_mean_abs_error_c':math.fsum(errors)/len(errors),
        'temperature_outside_product_range_rows':clamped,'max_voltage_float_error_v':max_voltage_error,
        'max_current_float_error_a':max_current_error,'loaded_charge_ah':math.fsum(charge)/3600,
        'interpretation':'exact loader conversion check, not lossless temperature or product pack acceptance'}


def save(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def run(candidate,loader,output):
    candidate=Path(candidate);loader=Path(loader).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'schema':'nasa-replay-candidates-v1','status':'INCOMPLETE','scope':'offline reconstruction and actual product loader comparison only',
        'selection':{'file':'B0028.mat','cycle_zero_based':3,'reason':'historical raw inspection comparison, no estimator-based selection'},
        'candidates':[],'policy_adopted':False,'product_pack_execution':False,'soc_accuracy_evaluated':False}
    identity={'candidate_sha256':digest(candidate),'loader_sha256':digest(loader),
        'source_sha256':{name:digest(ROOT/name) for name in SOURCES}}
    report['identity']=identity
    try:
        if identity['candidate_sha256']!=PIN:raise ValueError('historical source identity mismatch')
        raw=inspect_archive(candidate,output/'raw-inspection')
        path=output/'raw-inspection/B0028-cycle3-raw.csv'
        if digest(path)!=raw['selected_raw_csv_sha256']:raise ValueError('raw export hash mismatch')
        with path.open(newline='') as stream:
            reader=csv.DictReader(stream)
            if reader.fieldnames!=list(FIELDS):raise ValueError('exact raw schema required')
            source=list(reader)
        data={key:[float(row[column]) for row in source] for key,column in
            zip(('Time','Voltage_measured','Current_measured','Temperature_measured'),FIELDS)}
        for mode in ('linear','previous'):
            rows,stats=resample(data,mode);folder=output/mode;folder.mkdir()
            with (folder/'grid.csv').open('x',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(FIELDS);writer.writerows(rows)
            with (folder/'profile.csv').open('x',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(PROFILE);writer.writerows(row[1:] for row in rows)
            before=digest(folder/'profile.csv')
            loaded=subprocess.run([str(loader),'--profile',str(folder/'profile.csv'),'--samples',str(len(rows))],
                capture_output=True,text=True,timeout=10)
            (folder/'loader.csv').write_text(loaded.stdout);(folder/'loader.stderr').write_text(loaded.stderr)
            if loaded.returncode!=0 or before!=digest(folder/'profile.csv'):raise ValueError('loader execution/input integrity failed')
            comparison=score_loaded(rows,list(csv.DictReader(loaded.stdout.splitlines())))
            comparison['loaded_charge_minus_reconstruction_ah']=comparison['loaded_charge_ah']-stats['reference_reconstruction_charge_ah']
            stats['product_loader']=comparison
            stats['conservation_numeric_tolerance_ah']=1e-10
            stats['conservation_check']='PASS' if stats['absolute_conservation_error_ah']<=1e-10 else 'FAIL'
            report['candidates'].append(stats)
        if (identity['candidate_sha256']!=digest(candidate) or identity['loader_sha256']!=digest(loader) or
                identity['source_sha256']!={name:digest(ROOT/name) for name in SOURCES}):
            raise ValueError('source or executable changed during comparison')
        report['previous_minus_linear_charge_ah']=report['candidates'][1]['reference_reconstruction_charge_ah']-report['candidates'][0]['reference_reconstruction_charge_ah']
        report['status']='COMPARISON_COMPLETE' if all(c['conservation_check']=='PASS' for c in report['candidates']) else 'FAIL'
    except (OSError,ValueError,TypeError,KeyError,ImportError,subprocess.SubprocessError) as error:
        report.update(status='INVALID',error=str(error))
    report['files_sha256']={str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    save(output/'report.json',report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True);parser.add_argument('--loader-executable',required=True)
    parser.add_argument('--output-dir',required=True);args=parser.parse_args()
    try:
        report=run(args.candidate,args.loader_executable,args.output_dir);print(json.dumps(report))
        return {'COMPARISON_COMPLETE':0,'FAIL':1,'INVALID':2}[report['status']]
    except (OSError,ValueError) as error:
        print(json.dumps({'status':'INVALID','error':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
