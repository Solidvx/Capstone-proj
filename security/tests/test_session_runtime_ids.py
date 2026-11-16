import os
import pytest
from security.can_session import SessionContext,derive_keys,data_mac
from security.ids.session_context import ContextSource,PACKET
from security.ids.session_detector import SessionDetector
from security.ids.runtime_detector import Config,Observation

KEY=bytes(range(32))
CONTEXT=SessionContext(7,bytes(range(16)),bytes(range(16,32)))
RAW=bytes.fromhex('64c80f3cffec4100')


class Source:
    def __init__(self):
        self.context=CONTEXT;self.generation=1;self.keys=derive_keys(KEY,CONTEXT);self.boundary_ns=0;self.open=True;self.pending=None
    def poll(self,now):
        if self.pending is None:return False
        self.generation,self.keys=self.pending;self.pending=None;return True
    def ready(self,now):return self.open


def detector():return SessionDetector(Config(),Source())
def pair(det,counter,t,reverse=False,auth=None):
    proof=auth or data_mac(det.source.keys['data'],0x100,counter,RAW)+counter.to_bytes(4,'big')
    frames=[Observation(t,0x100,RAW),Observation(t+.001,0x102,proof)]
    if reverse:frames=[Observation(t,0x102,proof),Observation(t+.001,0x100,RAW)]
    return sum((det.observe(frame) for frame in frames),[])


def test_session_mac_global_order_replay_and_reverse_pair():
    det=detector()
    events=pair(det,1,0,True)+pair(det,3,.1)+pair(det,2,.2)
    assert not [event for event in events if event.attack_type]
    assert det.observation_ready(.202)
    events=pair(det,1,.3)
    assert [event.attack_type for event in events if event.reason=='SESSION_COUNTER_REPLAY']==[2]


def test_bad_mac_old_counter_is_not_replay_and_expiry_without_pair_is_unknown():
    det=detector();pair(det,1,0)
    events=pair(det,1,.2,auth=bytes(4)+(1).to_bytes(4,'big'))+det.tick(.302)
    assert not [event for event in events if event.attack_type==2]
    assert [event.attack_type for event in events if event.reason=='SESSION_MAC_FAIL']==[3]
    det=detector();det.observe(Observation(0,0x100,RAW))
    assert not [event for event in det.tick(.2) if event.attack_type]


def test_missing_context_budget_and_known_control_ids_do_not_claim_coverage():
    det=detector();det.source.open=False
    events=[]
    for i,cid in enumerate((0x300,0x301,0x302,0x303)):
        events+=det.observe(Observation(i*.01,cid,bytes(8)))
    assert not [event for event in events if event.attack_type]
    assert det.unavailable_reason(.1)==4
    det.source.open=True;det.max_checks=1
    pair(det,1,.2,auth=bytes(8));pair(det,2,.21,auth=bytes(8))
    assert det.unavailable_reason(.22)==5
    assert not [event for event in det.tick(.4) if event.reason=='SESSION_MAC_FAIL']


def test_local_context_source_checks_generation_and_requires_fresh_live_pipe():
    reader,writer=os.pipe();os.set_blocking(reader,False);os.set_blocking(writer,False)
    try:
        source=ContextSource(reader,KEY)
        packet=PACKET.pack(b'CSC1',1,1,0,0,CONTEXT.transfer_id,CONTEXT.nonce_b,CONTEXT.nonce_a)
        os.write(writer,packet)
        assert source.poll(.1) and source.ready(.1)
        assert source.keys==derive_keys(KEY,CONTEXT)
        assert not source.ready(3.1)
        os.write(writer,PACKET.pack(b'CSC1',1,1,0,0,8,CONTEXT.nonce_b,CONTEXT.nonce_a))
        with pytest.raises(ValueError,match='without generation'):source.poll(3.2)
    finally:os.close(reader);os.close(writer)


def test_continuing_flood_keeps_condition_present_in_each_observation_window():
    from security.ids.observation_window import ObservationWindow
    det=detector();window=ObservationWindow(0,detector_revision=4)
    masks=[]
    for i in range(8001):
        now=i/1000
        events=det.observe(Observation(now,0x080,bytes(8)))
        update=window.observe(i,frame_present=True,events=events,total_drops=0)
        if update:masks.append(update[0][48])
    assert len(masks)==8 and all(mask&8 for mask in masks)


def test_context_switch_resets_counter_and_identifies_witnessed_old_session_pair():
    det=detector();old_auth=data_mac(det.source.keys['data'],0x100,1,RAW)+(1).to_bytes(4,'big')
    pair(det,1,0)
    det.source.pending=(2,derive_keys(KEY,SessionContext(8,bytes(range(16,32)),bytes(range(16)))))
    det.update_context(.1)
    assert not [event for event in pair(det,1,.1) if event.attack_type]
    events=pair(det,1,.3,auth=old_auth)+det.tick(.402)
    assert [event.attack_type for event in events if event.reason=='SESSION_MAC_FAIL']==[2]


def test_isolated_fuzzy_spoof_and_flood_remain_distinct():
    det=detector();events=[]
    for index,cid in enumerate((0x050,0x060,0x070)):
        events+=det.observe(Observation(index*.01,cid,bytes(8)))
    assert {event.attack_type for event in events if event.attack_type}=={1}
    det=detector();events=det.observe(Observation(0,0x100,bytes.fromhex('ffc80f3cffec4100')))
    assert {event.attack_type for event in events if event.attack_type}=={3}
    det=detector();events=[]
    for i in range(120):events+=det.observe(Observation(i*.001,0x080,bytes(8)))
    assert {event.attack_type for event in events if event.attack_type}=={4}


def test_if_rejects_legacy_or_unattested_training_before_fitting(tmp_path):
    import hashlib,json
    from security.ids.runtime import train_model
    path=tmp_path/'normal.jsonl'
    path.write_text(''.join(json.dumps({'t':i*.1+offset,'can_id':cid,'data':RAW.hex()})+'\n' for i in range(40) for cid,offset in ((0x100,0),(0x102,.002))))
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'schema':'ids-normal-v2','status':'COMPLETE','protocol':'ICD-v1.6',
        'rejected_frames':0,'duration_s':4,'allowed_ids':[0x100,0x102],'accepted_frames':80,
        'capture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
    with pytest.raises(ValueError,match='manifest'):train_model(path,protocol='session-v2')
    with pytest.raises(ValueError,match='legacy'):train_model(path,manifest_path=manifest,protocol='session-v2')


def test_session_capture_validates_sparse_control_ids_without_requiring_periodic_events(tmp_path):
    import hashlib,json
    from security.capture_normal import validate_capture
    from security.ids.session_detector import SESSION_IDS
    path=tmp_path/'normal.jsonl';manifest=tmp_path/'manifest.json'
    rows=[{'t':i*.1+offset,'can_id':cid,'data':RAW.hex()} for i in range(40) for cid,offset in ((0x100,0),(0x102,.002))]
    rows.append({'t':.01,'can_id':0x302,'data':'00'*8});rows.sort(key=lambda row:row['t'])
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    manifest.write_text(json.dumps({'schema':'ids-normal-v2','status':'COMPLETE','protocol':'session-v2',
        'rejected_frames':0,'duration_s':4,'allowed_ids':sorted(SESSION_IDS),'accepted_frames':len(rows),
        'capture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
    assert validate_capture(path,manifest)['protocol']=='session-v2'


def test_receive_epoch_change_does_not_erase_authenticated_replay_memory():
    det=detector();pair(det,1,0)
    det.begin_live_epoch(.1)
    assert not det.observation_ready(.1)
    assert not det.raw[0x100] and not det.auth[0x100]
    events=pair(det,1,.2)
    assert [event.attack_type for event in events if event.reason=='SESSION_COUNTER_REPLAY']==[2]
    pair(det,2,.3)
    assert det.observation_ready(.302)


def test_discarded_receive_epoch_has_unknown_drop_count_and_breaks_quiet_coverage():
    from security.ids.observation_window import ObservationWindow
    from security.can_diagnostic import valid_body
    window=ObservationWindow(0)
    window.observe(100,frame_present=False,events=[],total_drops=0,unavailable_reason=3,unknown_drops=True)
    body,state=window.observe(1000,frame_present=True,events=[],total_drops=0)
    assert body[16:18]==bytes((2,3)) and body[40:44]==bytes.fromhex('ffffffff')
    assert state.healthy_span_ms==0 and valid_body(0x302,7,body)


def test_single_replay_candidate_gets_wire_reference_but_repetition_is_ambiguous():
    from security.ids.observation_window import ObservationWindow
    from security.ids.incident_status import IncidentStatus
    from security.can_diagnostic import valid_body
    det=detector();pair(det,1,0);events=pair(det,1,.2)
    proof=next(event for event in events if event.attack_type==2)
    assert len(bytes.fromhex(proof.reference_hex))==44 and proof.candidate_index>0
    window=ObservationWindow(0,detector_revision=4)
    window.observe(201,frame_present=True,events=events,total_drops=0)
    body,state=window.observe(1000,frame_present=True,events=[],total_drops=0)
    incident=IncidentStatus().update(body,state,window.last_evidence)[0]
    assert incident[60:]==bytes.fromhex(proof.reference_hex) and valid_body(0x302,4,incident)
    repeated=ObservationWindow(0,detector_revision=4)
    repeated.observe(201,frame_present=True,events=events,total_drops=0)
    repeated.observe(401,frame_present=True,events=pair(det,1,.4),total_drops=0)
    body,state=repeated.observe(1000,frame_present=True,events=[],total_drops=0)
    incident=IncidentStatus().update(body,state,repeated.last_evidence)[0]
    assert incident[60:]==bytes(44)
