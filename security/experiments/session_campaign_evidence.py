"""Evaluate session campaign evidence without a CAN device or SecOC key.

Each trial supplies its two observer slices (exactly one set of phase barriers),
the full IVI stream and its owned IDS generation log. Host A and B timestamps
are scoped independently. Payload matches are arrival candidates only. This
module does not launch actors or certify log provenance; the controller must
seal the owned files and confirm cleanup separately.
"""
from bisect import bisect_right
import hashlib
import json
import math
import os
from pathlib import Path

from security.can_diagnostic import valid_body
from security.experiments.test360_support import classification

CODES={'fuzzy':1,'replay':2,'spoofing':3,'flooding':4}
NAMES={'Fuzzy':1,'Replay':2,'Spoofing':3,'Flooding':4}
PHASES=('baseline','attack','post','idle')


def number(value):
    if isinstance(value,bool):raise ValueError('boolean timestamp')
    result=float(value)
    if not math.isfinite(result) or result<0:raise ValueError('invalid timestamp')
    return result


def integer(value):
    if isinstance(value,bool):raise ValueError('boolean integer')
    if isinstance(value,int):result=value
    elif isinstance(value,str) and value.isascii() and value.isdecimal():result=int(value)
    else:raise ValueError('invalid integer')
    if result<0:raise ValueError('negative integer')
    return result


def phases(records,run_id):
    rows=[row for row in records if row.get('result')=='PHASE']
    if [row.get('phase') for row in rows]!=list(PHASES) or any(row.get('run_id')!=run_id for row in rows):
        raise ValueError('trial requires one ordered set of owned phase barriers')
    times=[number(row['t']) for row in rows]
    if any(a>=b for a,b in zip(times,times[1:])):raise ValueError('phase clock not increasing')
    return times


class IndexedIdsLog:
    """One scan indexes trial byte ranges without retaining the event records.

    Out-of-order timestamps are allowed: each span encloses every matching row,
    and its iterator filters timestamps again. Bad timestamps anywhere invalidate
    every view, as they do when the original whole log is passed to evaluate.
    """
    def __init__(self,path,windows=()):
        self.path=Path(path);self.first=None;self.records=0;self.timestamp_error=None
        self.spans={tuple(window):None for window in windows}
        intervals=sorted(self.spans);starts=[a for a,_ in intervals];ends=[]
        for _,end in intervals:ends.append(max(ends[-1] if ends else 0,end))
        digest=hashlib.sha256()
        with self.path.open('rb') as stream:
            self.identity=self.signature(os.fstat(stream.fileno()))
            while True:
                offset=stream.tell();line=stream.readline(65538)
                if not line:break
                if not line.endswith(b'\n') or len(line)-1>65536:
                    raise ValueError('incomplete or oversized IDS event')
                row=json.loads(line)
                if not isinstance(row,dict):raise ValueError('IDS event object required')
                if self.first is None:
                    if row.get('result')!='START':raise ValueError('IDS START required')
                    self.first=row;self.header_end=stream.tell()
                elif row.get('result')=='START':raise ValueError('duplicate IDS START')
                self.records+=1;digest.update(line)
                if 'timestamp' not in row:continue
                try:stamp=number(row['timestamp'])
                except (ValueError,TypeError,OverflowError) as error:
                    self.timestamp_error=str(error);continue
                index=bisect_right(starts,stamp)-1
                while index>=0 and ends[index]>stamp:
                    key=intervals[index]
                    if stamp<key[1]:
                        span=self.spans[key]
                        self.spans[key]=(offset if span is None else span[0],stream.tell())
                    index-=1
            if self.first is None:raise ValueError('IDS START required')
            self.check(stream)
        self.sha256=digest.hexdigest()

    @staticmethod
    def signature(info):
        return info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns

    def check(self,stream):
        if (self.signature(os.fstat(stream.fileno()))!=self.identity or
            self.signature(self.path.stat())!=self.identity):
            raise ValueError('collected IDS file changed during evaluation')

    def rows(self,window=None):
        if self.timestamp_error is not None:raise ValueError(self.timestamp_error)
        try:
            with self.path.open('rb') as stream:
                self.check(stream)
                if window is not None:
                    yield self.first
                    span=self.spans[window]
                    if span is None:
                        self.check(stream);return
                    stream.seek(max(span[0],self.header_end));end=span[1]
                else:end=self.identity[2]
                while stream.tell()<end:
                    line=stream.readline(65538)
                    if not line.endswith(b'\n') or len(line)-1>65536:
                        raise ValueError('incomplete or oversized IDS event')
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('IDS event object required')
                    if window is None or ('timestamp' in row and window[0]<=number(row['timestamp'])<window[1]):
                        yield row
                self.check(stream)
        except OSError as error:raise ValueError('collected IDS file unavailable') from error

    def __iter__(self):return self.rows()

    def window(self,start,end):
        key=(start,end)
        if key not in self.spans:return self  # Malformed observer windows remain evaluate's responsibility.
        source=self
        class View:
            def __iter__(self):return source.rows(key)
        return View()


def signature(row):
    cid=integer(row['can_id']);payload=bytes.fromhex(row['data'])
    if cid>0x7ff or len(payload)>8:raise ValueError('invalid Classical CAN signature')
    return cid,payload.hex()


def evaluate(*,config,attack,trial,run_id,worker,observers,ivi,ids=None,ids_mode='off'):
    if config not in (1,2,3) or attack not in CODES or type(trial) is not int or trial<1:
        raise ValueError('invalid trial configuration')
    if ids_mode not in (('rules-only','rules+if') if config==3 else ('off',)):
        raise ValueError('explicit compatible IDS mode required')
    result={'schema':'session-trial-evidence-v1','config':config,'attack_type':attack,
        'trial':trial,'run_id':run_id,'protocol':'raw-unprotected' if config==1 else 'session-v2',
        'ids_mode':ids_mode,'status':'INVALID','invalid_reasons':[],
        'expected_attack_code':CODES[attack],'attack_sent':0,'remote_arrival':{},
        'ecu_ids_attack_codes':[],'ivi_diagnostic_attack_codes':[],'ivi_view_model_attack_codes':[],
        'ecu_ids_type_result':'NOT_EVALUATED','ivi_diagnostic_type_result':'NOT_EVALUATED',
        'ivi_view_model_type_result':'NOT_EVALUATED','model_evaluations':0,
        'ivi_baseline_publications':0,'ivi_attack_post_publications':0,
        'blocking_evaluated':False,'blocked':None,'attack_success':None,'detect_latency_s':None,
        'screen_pixels_evaluated':False,
        'note':'Owned product log claims; same-host time windows only. Remote payload matches do not authenticate an attacker. No blocking rate or cross-host latency inferred.'}
    reasons=result['invalid_reasons']
    try:
        if len(observers)!=2:raise ValueError('two node observer slices required')
        windows=[phases(rows,run_id) for rows in observers]
        a_base,a_attack,_,a_end=windows[0]
        b_base,b_attack,_,b_end=windows[1]
        if isinstance(ids,IndexedIdsLog):ids=ids.window(a_base,a_end)
        transmissions=[row for row in worker if row.get('result')=='TX' and row.get('trial')==trial]
        done=[row for row in worker if row.get('result')=='ATTACK_DONE' and row.get('trial')==trial]
        result['attack_sent']=len(transmissions)
        if not transmissions:reasons.append('NO_INJECTION')
        if len(done)!=1 or integer(done[0]['sent'])!=len(transmissions):
            reasons.append('ATTACK_COMPLETION_UNVERIFIED')
        elif integer(done[0]['tx_errors']):reasons.append('ATTACK_TX_ERRORS')
        signatures={signature(row) for row in transmissions}
        for name,rows,times in zip(('ecu','ivi'),observers,windows):
            start,exposure,_,end=times
            frames=[row for row in rows if row.get('result')=='OBS_FRAME' and start<=number(row['t'])<end]
            baseline=[row for row in frames if number(row['t'])<exposure]
            candidates=[row for row in frames if number(row['t'])>=exposure and signature(row) in signatures]
            drops=[integer(row['rx_dropped']) for row in rows if 'rx_dropped' in row]
            if not drops:reasons.append(name.upper()+'_DROPS_UNKNOWN')
            if any(a>b for a,b in zip(drops,drops[1:])):reasons.append(name.upper()+'_DROP_COUNTER_RESET')
            delta=max(drops,default=0)-min(drops,default=0)
            baseline_count=sum(row['can_id']==0x100 for row in baseline)
            result['remote_arrival'][name]={'matching_frames':len(candidates),
                'baseline_bms_frames':baseline_count,'rx_dropped':delta}
            if not baseline_count:reasons.append(name.upper()+'_NO_BASELINE')
            if not candidates:reasons.append(name.upper()+'_ARRIVAL_UNVERIFIED')
            if delta or any(row.get('error') for row in frames):reasons.append(name.upper()+'_CAPTURE_ERROR')
            if any(row['can_id']==0x200 for row in baseline):reasons.append('LEGACY_BASELINE_ALERT')
            if config!=3 and any(row['can_id']==0x200 and signature(row) not in signatures for row in frames):
                reasons.append('LEGACY_ALERT_IN_OFF_CONFIG')

        publications=[]
        if config==1:
            publications=[row for row in ivi if row.get('result')=='FRAME' and row.get('can_id')==0x100
                and row.get('process_result')==2 and b_base<=integer(row['timestamp_ns'])/1e9<b_attack]
            if any(row.get('result')=='SESSION_PUBLICATION' for row in ivi):reasons.append('WRONG_RECEIVER_PROTOCOL')
        else:
            service=[row for row in ivi if row.get('result')=='SESSION_PUBLICATION' and
                     b_base<=integer(row['t2_published_ns'])/1e9<b_end]
            if any(row.get('run_id')!=run_id for row in service):reasons.append('IVI_RUN_ID_MISMATCH')
            generations={integer(row['session_generation']) for row in service}
            if len(generations)!=1 or 0 in generations:reasons.append('SESSION_GENERATION_UNVERIFIED')
            sequences=[integer(row['measurement_sequence']) for row in service]
            if sequences!=sorted(set(sequences)):reasons.append('PUBLICATION_ORDER_INVALID')
            if any(row.get('valid') is not True or row.get('stale') is not False or
                   integer(row['t1_received_ns'])>integer(row['t2_published_ns']) for row in service):
                reasons.append('PUBLICATION_QUALITY_INVALID')
            publications=[row for row in service if integer(row['t2_published_ns'])/1e9<b_attack]
            result['ivi_attack_post_publications']=len(service)-len(publications)
            view=[row for row in ivi if row.get('result')=='VIEW_MODEL_PUBLICATION' and
                  b_base<=integer(row['t3_view_model_ns'])/1e9<b_end]
            published={integer(row['measurement_sequence']):row for row in service}
            for row in view:
                source=published.get(integer(row['measurement_sequence']))
                if source is None or any(integer(row[key])!=integer(source[key]) for key in ('t1_received_ns','t2_published_ns')) or \
                   integer(row['t2_published_ns'])>integer(row['t3_view_model_ns']):
                    reasons.append('VIEW_MODEL_LINK_UNVERIFIED')
            if not any(integer(row['t3_view_model_ns'])/1e9<b_attack for row in view):
                reasons.append('VIEW_MODEL_BASELINE_UNVERIFIED')
            result['ivi_view_model_attack_codes']=sorted({NAMES[name] for row in view
                if integer(row['t3_view_model_ns'])/1e9>=b_attack
                for name in str(row.get('security','')).split(' · ') if name in NAMES})
            baseline_types={NAMES[name] for row in view if integer(row['t3_view_model_ns'])/1e9<b_attack
                            for name in str(row.get('security','')).split(' · ') if name in NAMES}
            if baseline_types:reasons.append('VIEW_MODEL_BASELINE_NOT_QUIET')
        if not publications:reasons.append('IVI_BASELINE_NOT_PUBLISHED')
        result['ivi_baseline_publications']=len(publications)

        diagnostics=[]
        for row in ivi:
            if row.get('result')!='AUTHENTICATED_DIAGNOSTIC':continue
            received=integer(row['received_monotonic_ms'])/1000
            if received>=b_end:continue
            if integer(row['verified_monotonic_ms'])<integer(row['received_monotonic_ms']):
                raise ValueError('diagnostic verification predates reception')
            body=bytes.fromhex(row['body_hex']);session=bytes.fromhex(row['session_id'])
            if len(session)!=16 or not any(session) or not valid_body(0x302,integer(row['kind']),body):
                raise ValueError('invalid authenticated diagnostic log')
            # DiagnosticSender starts at0; only wrap/reuse in the same session
            # is forbidden. Do not confuse it with nonzero session IDs.
            if integer(row['sequence'])>0xffffffff:raise ValueError('diagnostic sequence outside uint32')
            if row['kind']==7 and (type(row.get('condition_mask')) is not int or row['condition_mask'] not in range(16)):
                raise ValueError('observation mask unavailable')
            diagnostics.append((received,row,body))
        relevant=[item for item in diagnostics if item[0]>=b_base]
        if config>1:
            sessions={row['session_id'] for _,row,_ in relevant}
            if len(sessions)!=1:reasons.append('DIAGNOSTIC_SESSION_UNVERIFIED')
            if not any(row['kind']==1 for _,row,_ in relevant):reasons.append('NODE_STATUS_UNVERIFIED')
        if config!=3:
            if any(row['kind'] in (4,7) for _,row,_ in relevant):reasons.append('IDS_ENABLED_IN_OFF_CONFIG')
            if result['ivi_view_model_attack_codes']:reasons.append('IDS_VISIBLE_IN_OFF_CONFIG')
        else:
            if ids is None:raise ValueError('owned IDS generation log required')
            starts=[row for row in ids if row.get('result')=='START']
            if len(starts)!=1 or starts[0].get('protocol')!='session-v2' or starts[0].get('mode')!=ids_mode:
                reasons.append('IDS_GENERATION_UNVERIFIED')
            scoped=[row for row in ids if 'timestamp' in row and a_base<=number(row['timestamp'])<a_end]
            anomalies=[row for row in scoped if row.get('result')=='ANOMALY' and row.get('attack_type') in range(1,5)]
            if any(number(row['timestamp'])<a_attack for row in anomalies):reasons.append('IDS_BASELINE_NOT_QUIET')
            result['ecu_ids_attack_codes']=sorted({row['attack_type'] for row in anomalies if number(row['timestamp'])>=a_attack})
            if any(row.get('result')=='RECEIVE_EPOCH_RESET' for row in scoped):reasons.append('IDS_CLOCK_RESET')
            ipc=[row for row in scoped if row.get('result')=='DIAGNOSTIC_IPC']
            if any(row.get('local_accepted') is not True for row in ipc):reasons.append('IDS_IPC_FAILURE')
            accepted={(integer(row['kind']),row['body_hex']) for row in ipc if row.get('local_accepted') is True}
            heartbeats=sorted((item for item in diagnostics if item[1]['kind']==7),key=lambda item:item[0])
            carry=[item for item in heartbeats if item[0]<=b_base]
            health=(carry[-1:] if carry else [])+[item for item in heartbeats if item[0]>b_base]
            if not health or health[0][0]>b_base or b_base-health[0][0]>=3:
                reasons.append('OBSERVATION_BASELINE_UNVERIFIED')
            if health:
                if len({row['session_id'] for _,row,_ in health}|sessions)!=1:reasons.append('OBSERVATION_SESSION_CHANGED')
                if len({body[:16] for _,_,body in health})!=1:reasons.append('IDS_SOURCE_CHANGED')
                times=[item[0] for item in health]+[b_end]
                if any(b-a>=3 for a,b in zip(times,times[1:])):reasons.append('OBSERVATION_GAP')
                ticks=[int.from_bytes(body[20:24],'big') for _,_,body in health]
                if ticks!=sorted(set(ticks)):reasons.append('OBSERVATION_ORDER_INVALID')
                if any(body[16]!=1 or row.get('observation_ready') is not True for _,row,body in health):
                    reasons.append('OBSERVATION_UNHEALTHY')
                if any(body[48] or row.get('condition_mask') for received,row,body in health if received<b_attack):
                    reasons.append('OBSERVATION_BASELINE_NOT_QUIET')
            delivered=set()
            for received,row,body in health:
                if received>=b_attack:
                    if (7,row['body_hex']) not in accepted:reasons.append('DIAGNOSTIC_IPC_LINK_UNVERIFIED')
                    else:delivered.update(code for code in range(1,5) if body[48] & (1<<(code-1)))
            result['ivi_diagnostic_attack_codes']=sorted(delivered)
            evaluations=[row for row in scoped if row.get('result')=='MODEL_EVALUATION']
            result['model_evaluations']=len(evaluations)
            if ids_mode=='rules+if' and (not evaluations or any(row.get('input_complete') is not True or
                    not math.isfinite(float(row['anomaly_score'])) for row in evaluations)):
                reasons.append('IF_EVALUATION_UNVERIFIED')
    except (ValueError,KeyError,TypeError,IndexError,OverflowError) as error:
        reasons.append('MALFORMED_OR_MISSING_EVIDENCE')
        result['evidence_error']=str(error)
    result['invalid_reasons']=sorted(set(reasons))
    result['status']='INVALID' if reasons else 'VALID'
    if config==3:
        for output,values in (('ecu_ids_type_result','ecu_ids_attack_codes'),
                              ('ivi_diagnostic_type_result','ivi_diagnostic_attack_codes'),
                              ('ivi_view_model_type_result','ivi_view_model_attack_codes')):
            result[output]='INVALID' if reasons else classification(result[values],CODES[attack])
        # Import after module initialization: response shares the strict parsers.
        from security.experiments.session_response import measure
        result['attack_response']=measure(attack=attack,code=CODES[attack],run_id=run_id,
            signatures=signatures if not reasons else set(),observer=observers[1] if not reasons else [],
            window=windows[1] if not reasons else None,diagnostics=diagnostics if not reasons else [],
            accepted=accepted if not reasons else set(),valid=not reasons,
            rejections=ivi if not reasons else ())
        result['detect_latency_s']=result['attack_response']['latency_s']
    else:
        result['attack_response']={'status':'NOT_EVALUATED','latency_s':None,'target_s':3.}
    return result
