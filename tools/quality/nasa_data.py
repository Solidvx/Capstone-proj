"""Independent scipy MAT inspection of the historically pinned NASA candidate.

Keep raw single-cell units/time. No resampling, pack EKF, SOC truth or source
selection based on estimation results. scipy is needed only by the CLI reader.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

PIN='7fa159be0c4e78d97233ef777587f46270d1389b5d8a21d33c6e7573a8c8e3b8'
MATS={
    'B0028.mat':'050c377e85a2c41165f2e2e0d22bf9575385dd8c835a713c27edb65af6bb25e8',
    'B0025.mat':'38894747a9c79d719e95a2e6c42be18017e29c522b760056b680a65105d1a15f',
    'B0026.mat':'ca5eee0b33d8070e3a6c254696444a0c65a12f40587fcfc8db858640b2e6e36c',
    'B0027.mat':'de2b4045ef20a6900885e169f3540664bb637f5f94b41fb4333c31d759237209'}
FIELDS=('Time','Voltage_measured','Current_measured','Temperature_measured')


def inspect_cycle(data):
    """Reject unknown shape/nonfinite values; do not trim or repair raw input."""
    arrays={}
    for key in FIELDS:
        if key not in data:raise ValueError('missing raw '+key)
        try:arrays[key]=[float(value) for value in data[key]]
        except (TypeError,ValueError,OverflowError):raise ValueError('raw vector required: '+key) from None
    lengths={key:len(values) for key,values in arrays.items()}
    if len(set(lengths.values()))!=1 or lengths['Time']<2:raise ValueError('array length mismatch or insufficient samples')
    nonfinite={key:sum(not math.isfinite(v) for v in values) for key,values in arrays.items()}
    if any(nonfinite.values()):raise ValueError('nonfinite raw values: '+json.dumps(nonfinite,sort_keys=True))
    times=arrays['Time'];gaps=[b-a for a,b in zip(times,times[1:])]
    if times[0]<0 or min(gaps)<=0:raise ValueError('negative/nonincreasing raw time')
    # Extra measured load/charger arrays and Capacity also require finite data.
    for key,value in data.items():
        if key in FIELDS:continue
        try:values=[float(v) for v in value] if hasattr(value,'__iter__') else [float(value)]
        except (TypeError,ValueError,OverflowError):raise ValueError('invalid extra raw field: '+key) from None
        if len(values) not in (1,len(times)) or not all(math.isfinite(v) for v in values):
            raise ValueError('invalid extra field length/nonfinite: '+key)
    return {'samples':len(times),'start_s':times[0],'end_s':times[-1],
        'duration_s':times[-1]-times[0],'min_gap_s':min(gaps),'max_gap_s':max(gaps),
        'range':{key:{'min':min(values),'max':max(values)} for key,values in arrays.items() if key!='Time'},
        'measured_current_trapezoid_ah':math.fsum((b-a)*(i+j)/2 for a,b,i,j in
            zip(times,times[1:],arrays['Current_measured'],arrays['Current_measured'][1:]))/3600,
        'raw_fields':sorted(data),
        'soc_named_field_present':any(key.lower() in ('soc','state_of_charge','stateofcharge') for key in data),
        'soc_ground_truth_established':False},arrays


def inspect_archive(candidate,output):
    from scipy.io import loadmat
    import scipy
    candidate=Path(candidate);data=candidate.read_bytes()
    if hashlib.sha256(data).hexdigest()!=PIN:raise ValueError('candidate hash differs from historical source')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'schema':'nasa-raw-inspection-v1','status':'RAW_INSPECTION_COMPLETE',
        'candidate_sha256':PIN,'scipy_version':scipy.__version__,'scope':'raw single-cell data inspection, no SOC accuracy or resampling acceptance',
        'units':dict(Time='seconds within one cycle',Voltage_measured='cell terminal volts',
            Current_measured='measured signed amperes',Temperature_measured='degrees Celsius'),
        'cells':{},'resampling_adopted':False,'product_loader_verified':False,'physical_accuracy_measured':False}
    selected=None
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if any(archive.namelist().count(name)!=1 for name in MATS):raise ValueError('missing/duplicate MAT member')
        if archive.testzip() is not None:raise ValueError('candidate CRC failure')
        for name,pin in MATS.items():
            raw=archive.read(name)
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('MAT hash mismatch: '+name)
            cycles=loadmat(io.BytesIO(raw),simplify_cells=True)[Path(name).stem]['cycle']
            kinds=Counter(str(row['type']) for row in cycles);checks=[]
            for index,cycle in enumerate(cycles):
                if cycle['type'] not in ('charge','discharge'):continue
                check={'cycle_zero_based':index,'type':cycle['type']}
                try:
                    value,arrays=inspect_cycle(cycle['data']);check.update(status='VALID',**value)
                    if name=='B0028.mat' and index==3:selected=(check,arrays)
                except ValueError as error:check.update(status='INVALID',reason=str(error))
                checks.append(check)
            report['cells'][name]=dict(mat_sha256=pin,cycles_total=len(cycles),type_counts=dict(kinds),
                evaluated_charge_discharge=len(checks),valid=sum(c['status']=='VALID' for c in checks),
                invalid=sum(c['status']=='INVALID' for c in checks),
                skipped_impedance=kinds.get('impedance',0),checks=checks)
    if selected is None:raise ValueError('historical comparison cycle missing/invalid')
    check,arrays=selected
    with (output/'B0028-cycle3-raw.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(('time_s','cell_voltage_v','current_a','temperature_c'))
        writer.writerows(zip(*(arrays[key] for key in FIELDS)))
    report['historical_comparison_cycle']=dict(file='B0028.mat',**check)
    report['selected_raw_csv_sha256']=hashlib.sha256((output/'B0028-cycle3-raw.csv').read_bytes()).hexdigest()
    report['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if hashlib.sha256(candidate.read_bytes()).hexdigest()!=PIN:raise ValueError('candidate changed during inspection')
    (output/'inspection.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    try:
        result=inspect_archive(args.candidate,args.output_dir)
        print(json.dumps({key:value for key,value in result.items() if key!='cells'},allow_nan=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,ImportError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
