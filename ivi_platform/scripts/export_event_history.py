#!/usr/bin/env python3
"""Export validated event summaries and a SHA-256 manifest; never alter the store."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ALLOWED={'ecu_protection','protection_link','ecu_process','ecu_restart_plan','typed_incidents','incident_rejection_ids','source_instance','origin','category','schema','event_id','recorded_utc','display','summary','session_generation','connection_stage',
         'battery_state','battery_reason','observation_ready','incident_ids','local_rejection_id',
         'local_rejection_reason','records_lost_before','previous_gap_possible'}
MAX_LINE=65536


def review_protection_fields(event):
    """Review the new summary shape; this does not reauthenticate CAN data."""
    if 'ecu_protection' not in event:
        if 'protection_link' in event:raise ValueError('protection link without reviewed summary')
        return
    p=event['ecu_protection']
    fields={'body_hex','instance_id','lineage_id','incident_id','state','reason','phase','revision',
            'checkpoint_resumed','state_confirmed','session_id','sequence','received_monotonic_ms'}
    if not isinstance(p,dict) or p.keys()-fields or fields-{'incident_id'}-p.keys():
        raise ValueError('unrecognized protection fields')
    for key,length in (('body_hex',112),('instance_id',32),('lineage_id',32),('session_id',32)):
        if not isinstance(p[key],str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',p[key]):
            raise ValueError('invalid protection hexadecimal field')
    for key,maximum in (('state',3),('reason',7),('phase',2)):
        if type(p[key]) is not int or not 0<=p[key]<=maximum:raise ValueError('invalid protection numeric field')
    if type(p['checkpoint_resumed']) is not bool or p['state_confirmed'] is not True:
        raise ValueError('unconfirmed protection summary')
    for key,maximum in (('revision',0xFFFFFFFF),('sequence',0xFFFFFFFF),('received_monotonic_ms',0xFFFFFFFFFFFFFFFF)):
        value=p[key]
        if not isinstance(value,str) or not re.fullmatch('0|[1-9][0-9]*',value) or int(value)>maximum:
            raise ValueError('invalid protection counter')
    if bool(p['phase']) != ('incident_id' in p) or ('incident_id' in p and
            (not isinstance(p['incident_id'],str) or not re.fullmatch('[0-9a-f]{32}',p['incident_id']))):
        raise ValueError('invalid protection incident identity')
    if 'protection_link' not in event:return
    link=event['protection_link']
    fields={'status','previous_event_id','previous_revision','high_water_revision','gap_possible',
            'prior_record_id','prior_event_end_unconfirmed'}
    statuses={'unlinked','updated','resumed','reconnected','checkpoint-history-gap','new-lineage','new-incident'}
    if not isinstance(link,dict) or link.keys()-fields or not {'status','high_water_revision','gap_possible'}<=link.keys():
        raise ValueError('unrecognized protection link fields')
    if not isinstance(link['status'],str) or link['status'] not in statuses or type(link['gap_possible']) is not bool:
        raise ValueError('invalid protection link status')
    for key in ('high_water_revision','previous_revision'):
        if key not in link:continue
        value=link[key]
        if not isinstance(value,str) or not re.fullmatch('0|[1-9][0-9]*',value) or int(value)>0xFFFFFFFF:
            raise ValueError('invalid protection link revision')
    if int(link['high_water_revision'])<int(p['revision']):raise ValueError('protection high-water rollback')
    for key in ('previous_event_id','prior_record_id'):
        if key in link and (not isinstance(link[key],str) or not re.fullmatch(
                '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',link[key])):
            raise ValueError('invalid protection linked record identity')
    if 'prior_event_end_unconfirmed' in link and type(link['prior_event_end_unconfirmed']) is not bool:
        raise ValueError('invalid protection prior-end flag')


def export(directory,out):
    info=directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('private owned store required')
    files=sorted(directory.glob('events-*.jsonl'))
    if len(files)>4096 or any(not re.fullmatch(r'events-[0-9]{20}\.jsonl',p.name) for p in files):raise ValueError('invalid segment list')
    out.mkdir(mode=0o700,parents=False,exist_ok=False)
    temporary=out/'events.pending';previous=0;rows=0;partial=[];sources=[];gaps=False
    try:
        with temporary.open('xb') as target:
            os.chmod(temporary,0o600)
            for path in files:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as source:
                    info=os.fstat(source.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('source permissions/type rejected')
                    remaining=info.st_size;digest=hashlib.sha256()
                    while remaining:
                        line=source.readline(min(MAX_LINE+1,remaining));remaining-=len(line);digest.update(line)
                        if not line:raise ValueError('source changed while exporting')
                        if len(line)>MAX_LINE:raise ValueError('oversized event row')
                        if not line.endswith(b'\n'):partial.append(path.name);break
                        record=json.loads(line);sequence=record['sequence'];payload=record['payload']
                        if record.get('schema')!=1 or not isinstance(sequence,str) or not sequence.isascii() or not sequence.isdecimal() or int(sequence)<=previous:
                            raise ValueError('invalid event sequence/schema')
                        if hashlib.sha256((sequence+'\n'+payload).encode()).hexdigest()!=record['sha256']:raise ValueError('checksum mismatch')
                        event=json.loads(payload)
                        if not isinstance(event,dict) or event.keys()-ALLOWED:raise ValueError('unrecognized fields; review before export')
                        review_protection_fields(event)
                        gaps|=bool(event.get('previous_gap_possible') or event.get('records_lost_before') or
                                   event.get('protection_link',{}).get('gap_possible'))
                        target.write((json.dumps({'sequence':sequence,'event':event},ensure_ascii=False,separators=(',',':'))+'\n').encode())
                        previous=int(sequence);rows+=1
                    sources.append({'name':path.name,'bytes_at_open':info.st_size,'sha256_prefix':digest.hexdigest()})
            target.flush();os.fsync(target.fileno())
        final=out/'events.jsonl';temporary.rename(final)
        checksum=hashlib.sha256()
        with final.open('rb') as exported:
            for chunk in iter(lambda:exported.read(65536),b''):checksum.update(chunk)
        manifest={'schema':'ivi-event-export-v1','status':'COMPLETE_WITH_PARTIAL_TAILS' if partial else 'COMPLETE',
            'writer_marker_present':os.path.lexists(directory/'writer-active'),'contains_gap_annotations':gaps,
            'coverage':'verified segment prefixes; uncommitted memory queue is outside export',
            'records':rows,'sha256':checksum.hexdigest(),'partial_tail_files':partial,
            'source_prefixes':sources,'scope':'validated summaries read at each segment open; live app may continue writing; no source deletion'}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        return manifest
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(export(args.directory,args.out),ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
