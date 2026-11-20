"""Score every captured raw BMS interval; never infer ECU TX or physical timing.

Input is the raw observer evidence from common/test_bms_period_product.py.
Kernel CLOCK_REALTIME stamps are mapped once to this host's monotonic epoch;
clock mapping changes, collection loss or incomplete captures invalidate it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


def analyze(rows, manifest):
    if manifest.get('schema')!='bms-period-capture-v1':raise ValueError('unknown capture schema')
    if manifest.get('environment') not in ('vcan','physical-can'):raise ValueError('explicit environment required')
    if manifest.get('clock')!='kernel-realtime-mapped-to-local-monotonic-ns':raise ValueError('kernel clock evidence required')
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',str(manifest.get('boot_id',''))):
        raise ValueError('Linux boot identity required')
    def uint(value):return type(value) is int and 0<=value<2**64
    if not all(uint(manifest.get(name)) for name in ('start_ns','end_ns','rx_dropped','interface_rx_dropped','clock_mapping_max_change_ns')):
        raise ValueError('complete nonnegative integer capture metadata required')
    if manifest['end_ns']<=manifest['start_ns']:raise ValueError('capture boundary order')
    reasons=[]
    if manifest.get('status')!='COMPLETE':reasons.append('CAPTURE_INCOMPLETE')
    if manifest.get('normal_attested') is not True:reasons.append('NORMAL_INPUT_UNCONFIRMED')
    if manifest['rx_dropped'] or manifest['interface_rx_dropped']:reasons.append('CAPTURE_DROPS')
    if manifest['clock_mapping_max_change_ns']>10_000_000:reasons.append('CLOCK_MAPPING_CHANGED')
    times=[];error_frames=0;malformed_bms=0;previous=None
    for row in rows:
        stamp=row.get('received_ns');cid=row.get('can_id');dlc=row.get('dlc')
        if (not uint(stamp) or not manifest['start_ns']<=stamp<=manifest['end_ns'] or
                not uint(cid) or cid>0x1fffffff or not uint(dlc) or dlc>8 or
                not all(type(row.get(flag)) is bool for flag in ('extended','remote','error')) or
                not isinstance(row.get('data'),str) or not re.fullmatch('[0-9a-f]*',row['data']) or len(row['data'])!=dlc*2):
            raise ValueError('invalid raw frame or capture boundary')
        if previous is not None and stamp<previous:raise ValueError('capture timestamp regressed')
        previous=stamp;error_frames+=int(row['error'])
        if cid==0x100:
            if row['extended'] or row['remote'] or row['error'] or dlc!=8:malformed_bms+=1
            else:times.append(stamp)
    if error_frames:reasons.append('CAN_ERROR_FRAMES')
    if malformed_bms:reasons.append('MALFORMED_BMS')
    gaps=[b-a for a,b in zip(times,times[1:])]
    if len(gaps)<100:reasons.append('FEWER_THAN_100_INTERVALS')
    violations=[{'interval':i+1,'start_ns':times[i],'end_ns':times[i+1],'gap_ms':gap/1e6}
                for i,gap in enumerate(gaps) if not 90_000_000<=gap<=110_000_000]
    return {'schema':'bms-period-report-v1','status':'INVALID' if reasons else 'FAIL' if violations else 'PASS',
        'scope':'raw 0x100 observer inter-arrival intervals, not ECU send timestamps',
        'environment':manifest['environment'],'boot_id':manifest['boot_id'],
        'frames_total':len(rows),'bms_frames':len(times),'intervals':len(gaps),
        'error_frames':error_frames,'malformed_bms':malformed_bms,'invalid_reasons':reasons,
        'criterion':{'minimum_intervals':100,'lower_ms':90,'upper_ms':110,'all_intervals_required':True},
        'metrics':{'min_ms':min(gaps)/1e6 if gaps else None,'max_ms':max(gaps)/1e6 if gaps else None,
            'mean_ms':statistics.mean(gaps)/1e6 if gaps else None,
            'stddev_ms':statistics.pstdev(gaps)/1e6 if gaps else None},
        'violations':violations,'physical_tc_acceptance':False,
        'note':'No trimming, averaging away outliers, TX success, physical bus load or cryptographic sender attribution inferred. Physical TC acceptance also requires apparatus and sender/capture-loss review.'}


def evaluate(directory, output):
    directory=Path(directory);raw=directory/'frames.jsonl';meta=directory/'capture.json'
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw,meta)}
    manifest=json.loads(meta.read_text())
    if before[raw.name]!=manifest.get('frames_sha256'):raise ValueError('capture hash mismatch')
    rows=[json.loads(line) for line in raw.read_text().splitlines()]
    result=analyze(rows,manifest)
    if before!={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw,meta)}:
        raise ValueError('capture changed during evaluation')
    result['files_sha256']=before
    result['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with Path(output).open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        report=evaluate(args.input_dir,args.output);print(json.dumps(report))
        return {'PASS':0,'FAIL':1,'INVALID':2}[report['status']]
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
