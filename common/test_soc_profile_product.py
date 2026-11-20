"""Actual fixed S-21 CSV→product SensorSimulator/EKF, without CAN or keys."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import csv
import struct
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.quality.bms_profile import run
from tools.quality.sensor_scenarios import run as run_source_cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluator',required=True,type=Path)
    parser.add_argument('--profile-loader',required=True,type=Path)
    parser.add_argument('--out-parent',required=True,type=Path)
    args=parser.parse_args();args.out_parent.mkdir(parents=True,exist_ok=True)
    base=Path(tempfile.mkdtemp(prefix='soc-profile-',dir=args.out_parent))
    report=run(args.evaluator,base/'campaign')
    assert report['status']=='PASS' and report['completed_cases']==7,report.get('error','fixed criteria failed')
    assert all(case['samples']==36000 and case['duration_s']==3600 for case in report['cases'])
    assert all(abs(case['reference_final_soc_pct']-76)<1e-10 for case in report['cases'])
    assert sum(case['strict_improvement_required'] for case in report['cases'])==2
    assert sum(case['role']=='sensitivity' for case in report['cases'])==4
    # A short CSV may not silently hold its final row to fill missing samples.
    profile=base/'short.csv';profile.write_text('voltage_v,current_a,temperature_c\n40,-2,25\n39,-2,25\n')
    for label,options in [('short',['--profile',str(profile),'--samples','3']),
                          ('empty_count',['--profile',str(profile),'--samples','0']),
                          ('too_large',['--profile',str(profile),'--samples','36001']),
                          ('partial_integer',['--profile',str(profile),'--samples','2x']),
                          ('missing',['--profile',str(base/'missing.csv'),'--samples','2'])]:
        result=subprocess.run([str(args.evaluator.resolve())]+options,capture_output=True,timeout=5)
        (base/(label+'.stdout')).write_bytes(result.stdout);(base/(label+'.stderr')).write_bytes(result.stderr)
        assert result.returncode==2 and not result.stdout,label
    emitted=subprocess.run([str(args.evaluator.resolve()),'--profile',str(profile),'--samples','2','--emit-bms'],
        capture_output=True,text=True,timeout=5)
    (base/'emit-bms.stdout').write_text(emitted.stdout);(base/'emit-bms.stderr').write_text(emitted.stderr)
    assert emitted.returncode==0
    encoded=list(csv.DictReader(emitted.stdout.splitlines()))
    assert len(encoded)==2 and [int(row['bms_payload_hex'][4:8],16) for row in encoded]==[4000,3900]
    assert all(row['bms_payload_hex'][2:4]=='c8' and row['bms_payload_hex'][8:]=='ffec4100' for row in encoded)
    rejected=subprocess.run([str(args.evaluator.resolve()),'--profile',str(profile),'--samples','2','--unknown-output'],capture_output=True,timeout=5)
    assert rejected.returncode==2 and not rejected.stdout
    invalid=base/'nonfinite.csv';invalid.write_text('voltage_v,current_a,temperature_c\n40,nan,25\n')
    result=subprocess.run([str(args.evaluator.resolve()),'--profile',str(invalid),'--samples','1'],capture_output=True,timeout=5)
    (base/'nonfinite.stdout').write_bytes(result.stdout);(base/'nonfinite.stderr').write_bytes(result.stderr)
    assert result.returncode==2 and len(result.stdout.splitlines())<=1
    # Real loader boundary: fractional/negative half ties and clamp limits.
    # Cell voltages are not multiplied into virtual pack measurements.
    probe=base/'loader-input.csv'
    probe.write_text('voltage_v,current_a,temperature_c\n4.181907184700754,-1.9969349193365222,26.5\n'
                     '2.6151397684307285,0.003953073598938974,-9.5\n4,-2,70.6\n')
    loaded=subprocess.run([str(args.profile_loader.resolve()),'--profile',str(probe),'--samples','3'],
                          capture_output=True,text=True,timeout=5)
    (base/'loader.stdout').write_text(loaded.stdout);(base/'loader.stderr').write_text(loaded.stderr)
    assert loaded.returncode==0
    values=list(csv.DictReader(loaded.stdout.splitlines()))
    f32=lambda value:struct.unpack('f',struct.pack('f',value))[0]
    assert len(values)==3 and [int(row['temperature_c']) for row in values]==[27,-10,70]
    assert float(values[0]['voltage_v'])==f32(4.181907184700754)
    assert float(values[1]['current_a'])==f32(0.003953073598938974)
    for label,options in [('short',['--profile',str(probe),'--samples','4']),
                          ('invalid_count',['--profile',str(probe),'--samples','3x']),
                          ('missing',['--profile',str(base/'missing.csv'),'--samples','3'])]:
        failed=subprocess.run([str(args.profile_loader.resolve())]+options,capture_output=True,timeout=5)
        (base/('loader-'+label+'.stderr')).write_bytes(failed.stderr)
        assert failed.returncode==2 and not failed.stdout
    # Separate supplemental source faults; no labels passed to the native child.
    supplemental=run_source_cases(args.evaluator,base/'source-supplement',
        {'schema':'sensor-source-supplement-v1','samples':100,'event_start':20,'event_end':70,
            'drift_final_bias_v':-.5,'jump_bias_v':-6.,'mismatch_current_bias_a':4.})
    assert supplemental['status']=='COMPLETE' and len(supplemental['cases'])==6
    assert all(row['dummy_authenticated_pairs']=={'legacy':100,'session':100} for row in supplemental['cases'])
    assert all(not row['labels_used_by_detectors'] for row in supplemental['cases'])
    for row in supplemental['cases'][:2]:
        assert not row['legacy_attack_type_counts'] and not row['session_attack_type_counts']
    control=supplemental['cases'][0];frozen=next(row for row in supplemental['cases'] if row['case']=='voltage_freeze')
    assert control['dummy_frame_stream_sha256']==frozen['dummy_frame_stream_sha256']
    summary={'status':'PASS','scope':report['scope'],'cases':7,'updates_per_case':36000,
        'primary_criteria_passed':2,'sensitivity_cases_preserved':4,'error_cases_checked':7,
        'supplemental_source_cases':6,'supplemental_sample_count':100,
        'supplemental_report_sha256':hashlib.sha256((base/'source-supplement/report.json').read_bytes()).hexdigest(),
        'native_executable_sha256':report['identity']['executable_sha256'],
        'profile_loader_boundary_cases':4,
        'profile_loader_executable_sha256':hashlib.sha256(args.profile_loader.read_bytes()).hexdigest(),
        'campaign_report_sha256':hashlib.sha256((base/'campaign/report.json').read_bytes()).hexdigest(),
        'not_measured':report['not_measured']}
    (base/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(summary,output=str(base))))
    return 0


if __name__=='__main__':raise SystemExit(main())
