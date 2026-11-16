"""Decision-time evidence must describe the check without changing its verdict."""
from dataclasses import asdict
import hashlib
import hmac
import json
import struct
import uuid

import pytest

from security.ids.runtime import run_replay
from security.ids.runtime_detector import Config,Event,ModelEvaluation,Observation,RuntimeDetector
from security.ids.session_detector import SessionDetector
from security.tests.test_session_runtime_ids import Source,RAW,pair

KEY=bytes(range(32)) # Explicit public dummy; never device key material.


def pick(events,reason):
    return next(event for event in events if event.reason==reason)


def test_raw_period_uses_configured_limit_and_actual_interval():
    detector=RuntimeDetector(Config(min_period_s=.075))
    detector.observe(Observation(0,0x100,RAW))
    event=pick(detector.observe(Observation(.05,0x100,RAW)),'PERIOD_TOO_SHORT')
    assert event.finding['observed']=={'raw_interval_s':.05}
    assert event.finding['expected']=={'minimum_s':.075}
    assert event.finding['unit']=='seconds' and event.attack_type==0
    assert event.alert_payload(0) is None


def test_missing_is_raw_timer_evidence_not_authenticated_freshness():
    detector=RuntimeDetector(Config(missing_s=.4))
    detector.observe(Observation(.1,0x100,RAW))
    event=pick(detector.tick(.6),'MESSAGE_MISSING')
    assert event.finding['origin']=='raw-timer'
    assert event.finding['observed']=={'last_raw_received_s':.1,'elapsed_s':.5}
    assert event.finding['expected']=={'missing_at_s':.4}
    assert event.finding['authentication']=='not_checked' and event.attack_type==0


@pytest.mark.parametrize('observation,reason',[
    (Observation(0,0x800,RAW),'FRAME_FORMAT'),
    (Observation(0,0x100,RAW[:7],7),'DLC'),
    (Observation(0,0x777,RAW),'UNKNOWN_ID'),
    (Observation(0,0x100,bytes.fromhex('ffc80f3cffec4101')),'BMS_RANGE'),
    (Observation(0,0x101,bytes.fromhex('040900fffe010203')),'FAILSAFE_RANGE'),
])
def test_format_and_range_findings_use_bounded_needed_values(observation,reason):
    event=pick(RuntimeDetector().observe(observation),reason)
    row=asdict(event);finding=row['finding']
    assert finding['observed'] is not None and finding['expected'] is not None and finding['unit']
    assert finding['schema']=='ids-finding-v1' and finding['profile']=='legacy-v1'
    assert uuid.UUID(hex=finding['source_id']).version==4
    assert finding['severity'] is None and finding['severity_policy']=='not_calibrated'
    serialized=json.dumps(row,allow_nan=False)
    assert len(serialized)<4096 and RAW.hex() not in serialized and KEY.hex() not in serialized


def test_jump_retains_previous_raw_values_and_individual_delta_units():
    detector=RuntimeDetector(Config(max_soc_step=7))
    detector.observe(Observation(0,0x100,RAW))
    altered=bytes([150])+RAW[1:]
    event=pick(detector.observe(Observation(.1,0x100,altered)),'BMS_STEP')
    assert event.finding['observed']['absolute_delta'][0]==25
    assert event.finding['expected']['maximum_delta'][0]==7
    assert event.finding['unit']['absolute_delta']==['percentage_points','celsius','ampere']
    assert event.finding['unit']['previous_raw_values'][0]=='percent'
    assert event.attack_type==3


def test_rate_records_count_not_an_unmeasured_bus_load_or_timing_rate():
    detector=RuntimeDetector(Config(max_frames_per_second=3))
    events=[]
    for t in (0,.01,.02):events+=detector.observe(Observation(t,0x80,bytes(8)))
    event=pick(events,'FRAME_RATE')
    assert event.finding['observed']=={'frame_count':3,'dominant_id':0x80,'dominant_count':3,'dominant_known':False}
    assert event.finding['expected']['rate_at_count']==3 and event.finding['unit']['frame_count']=='frames_in_window'
    assert event.attack_type==4


def test_finding_source_epoch_and_sequence_cannot_alias_after_receive_reset():
    detector=RuntimeDetector()
    first=pick(detector.observe(Observation(0,0x777,RAW)),'UNKNOWN_ID').finding
    detector.begin_live_epoch(.1)
    second=pick(detector.observe(Observation(.1,0x777,RAW)),'UNKNOWN_ID').finding
    assert first['source_id']==second['source_id'] and second['sequence']>first['sequence']
    assert (first['capture_epoch'],second['capture_epoch'])==(0,1)
    detector.finding_sequence=0xffffffffffffffff
    third=pick(detector.observe(Observation(.2,0x777,RAW)),'UNKNOWN_ID').finding
    assert third['source_id']!=second['source_id'] and third['sequence']==1


def legacy_pair(counter=0):
    auth=hmac.new(KEY,struct.pack('>HI',0x100,counter)+RAW,hashlib.sha256).digest()[:4]+counter.to_bytes(4,'big')
    return Observation(0,0x100,RAW),Observation(.001,0x102,auth)


def test_legacy_counter_is_explicitly_unverified_but_mac_failure_is_checked():
    detector=RuntimeDetector(key=KEY);raw,auth=legacy_pair()
    detector.observe(raw);detector.observe(auth)
    detector.observe(Observation(.1,0x100,RAW))
    reused=pick(detector.observe(Observation(.101,0x102,auth.data)),'COUNTER_REUSE')
    assert reused.finding['authentication']=='not_checked'
    assert reused.finding['observed']['delta_u32']==0
    raw,auth=legacy_pair(1);detector.observe(Observation(.2,raw.can_id,raw.data))
    bad=bytes([auth.data[0]^1])+auth.data[1:]
    event=pick(detector.observe(Observation(.201,auth.can_id,bad)),'MAC_FAIL')
    assert event.finding['authentication']=='failed' and event.finding['observed']['tag_matches'] is False
    assert bad.hex() not in json.dumps(event.finding) and KEY.hex() not in json.dumps(event.finding)


def test_session_replay_is_verified_but_expiry_does_not_claim_mac_failure():
    detector=SessionDetector(Config(),Source());pair(detector,1,0)
    replay=pick(pair(detector,1,.1),'SESSION_COUNTER_REPLAY')
    assert replay.finding['authentication']=='verified' and replay.finding['profile']=='session-v2'
    assert replay.finding['observed']['counter']==1 and replay.finding['observed']['counter_seen']
    assert replay.reference_hex and replay.evidence_bits==4
    detector.observe(Observation(.3,0x100,RAW))
    expired=pick(detector.tick(.41),'SESSION_PAIR_EXPIRED')
    assert expired.finding['observed']['candidate_side']=='original'
    assert expired.finding['authentication']=='not_checked' and expired.attack_type==0


def test_model_scores_and_feature_units_are_actual_outputs_without_extra_inference():
    class Model:
        calls=[]
        def anomaly(self,features):self.calls.append('anomaly');return .25
        def wire_score(self,features):self.calls.append('wire');return 81
    model=Model();detector=SessionDetector(Config(),Source(),model)
    detector.observe(Observation(.1,0x100,RAW))
    events=detector.tick(1)
    evaluated=pick(events,'IF_WINDOW');anomaly=pick(events,'IF_ANOMALY')
    assert isinstance(evaluated,ModelEvaluation) and isinstance(evaluated,Event)
    assert evaluated.finding['observed']['anomaly']==.25
    assert evaluated.finding['observed']['features']['msg_rate']==1
    assert evaluated.finding['unit']['features']['msg_rate']=='frames_in_window'
    assert evaluated.finding['unit']['features']['payload_change']=='changed_bytes_per_pair'
    assert evaluated.finding['model_identity_reference']=='START.startup_identity.trained_model_sha256'
    assert evaluated.features==(1.,0.,0.,1.,0.,0.,1.) and model.calls==['anomaly','wire']
    assert anomaly.finding['observed']['normalized_wire_score']==.81 and anomaly.alert_payload(0) is None


def test_replay_writer_retains_finding_with_core_event_and_unique_id():
    import io
    output=io.StringIO();detector=RuntimeDetector()
    run_replay(detector,[Observation(0,0x777,RAW)],output)
    row=json.loads(output.getvalue())
    assert row['reason']=='UNKNOWN_ID' and row['attack_type']==0
    assert row['finding']['observed']['can_id']==0x777 and row['finding']['sequence']==1


def test_burst_and_orphan_counts_are_local_failures_not_ivi_rejections():
    detector=RuntimeDetector(Config(failure_repeat_count=3),KEY)
    events=[]
    for t in (0,.01,.02):events+=detector.observe(Observation(t,0x102,bytes(8)))
    orphan=pick(events,'AUTH_ORPHAN');burst=pick(events,'SECOC_FAILURE_BURST')
    assert orphan.finding['observed']=={'pending_original':False}
    assert orphan.finding['authentication']=='not_checked'
    assert burst.finding['observed']['failures_in_window']==3
    assert burst.finding['expected']=={'emit_at_count':3}
    assert burst.finding['origin']=='local-secoc' and burst.attack_type==0


def test_session_budget_uncertainty_does_not_add_a_context_read_or_fake_mac_failure():
    class CountedSource(Source):
        reads=0
        def ready(self,now):self.reads+=1;return super().ready(now)
    source=CountedSource();detector=SessionDetector(Config(),source,max_checks=1)
    detector.observe(Observation(0,0x100,RAW))
    detector.observe(Observation(.001,0x102,bytes(8))) # one MAC comparison fails
    detector.observe(Observation(.01,0x101,bytes.fromhex('0001016441000000')))
    budget=pick(detector.observe(Observation(.011,0x103,bytes(8))),'SESSION_MAC_BUDGET')
    assert budget.finding['observed']['checks_in_window']==budget.finding['expected']['maximum_checks']==1
    source.reads=0;events=detector.tick(.12)
    uncertain=pick(events,'SESSION_PAIR_UNCERTAIN')
    assert uncertain.finding['observed']=={'context_ready':None,'mac_budget_exhausted':True}
    assert uncertain.finding['authentication']=='not_checked' and source.reads==0
    assert not any(event.reason=='SESSION_MAC_FAIL' for event in events)


def test_session_candidate_limit_captures_pre_append_size_and_real_capacity():
    detector=SessionDetector(Config(),Source());events=[]
    for i in range(5):events+=detector.observe(Observation(i*.01,0x100,RAW))
    event=pick(events,'SESSION_CANDIDATE_LIMIT')
    assert event.finding['observed']=={'candidate_count_before_append':4,'side':'original'}
    assert event.finding['expected']=={'capacity':4} and detector.budget_exhausted


def test_metadata_does_not_remove_existing_event_hashability():
    event=pick(RuntimeDetector().observe(Observation(0,0x777,RAW)),'UNKNOWN_ID')
    assert hash(event)==hash(Event(event.timestamp,event.can_id,event.reason,event.attack_type,event.anomaly_score,event.result))
