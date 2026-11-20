"""Type separation with authenticated dummy normal traffic, without scenario hints in IDS."""
import random
import pytest
from security.experiments.can_attack_worker import injection_frames
from security.ids.runtime_detector import RuntimeDetector, Observation
from security.tests.test_runtime_ids import KEY, BMS, auth


def events_for(attack, profile='isolated-v1'):
    stream=[]
    for i in range(50):
        stream += [Observation(i*.1,0x100,BMS), Observation(i*.1+.001,0x102,auth(i))]
    rng=random.Random(71)
    rate=1000 if attack=='flooding' or profile=='mixed-v1' else 5
    pair=[(0x100,BMS),(0x102,auth(1))]
    for i in range(3*rate):
        for j,(cid,data) in enumerate(injection_frames(attack,rng,i,pair if attack=='replay' else None,profile)):
            stream.append(Observation(1.025+i/rate+j*.0001,cid,data))
    detector=RuntimeDetector(key=KEY)
    events=[e for frame in sorted(stream,key=lambda r:r.t) for e in detector.observe(frame)]
    return {e.attack_type for e in events if e.attack_type},events


@pytest.mark.parametrize('attack,code',[('flooding',4),('fuzzy',1),('replay',2),('spoofing',3)])
def test_separated_profiles_have_single_type(attack,code):
    codes,_=events_for(attack)
    assert codes=={code}


@pytest.mark.parametrize('attack,code',[('flooding',4),('fuzzy',1),('replay',2),('spoofing',3)])
def test_high_rate_profiles_have_single_type(attack,code):
    codes,_=events_for(attack,'mixed-v1')
    assert codes=={code}


@pytest.mark.parametrize('profile',['isolated-v1','mixed-v1'])
def test_random_attack_order_in_one_session_keeps_each_trial_single_type(profile):
    # One detector for the whole session: campaign phases (baseline 2 s, attack 3 s, post 1 s).
    rng=random.Random(5)
    schedule=[a for a in ('flooding','fuzzy','replay','spoofing') for _ in range(6)]
    rng.shuffle(schedule)
    plan,t=[],0.0
    for attack in schedule:
        a0=t+2+(1 if attack=='replay' else 0)
        plan.append((attack,t,a0,a0+4));t=a0+4
    stream=[]
    for i in range(int(t/.1)+1):
        stream += [Observation(i*.1,0x100,BMS), Observation(i*.1+.001,0x102,auth(i+1))]
    for n,(attack,_,a0,_) in enumerate(plan):
        raw=next(f for f in stream if f.can_id==0x100 and f.t>=a0-1)
        pair=[(0x100,raw.data),(0x102,auth(round(raw.t/.1)+1))]
        rate=1000 if attack=='flooding' or profile=='mixed-v1' else 5
        arng=random.Random(n)
        for i in range(3*rate):
            for j,(cid,data) in enumerate(injection_frames(attack,arng,i,pair if attack=='replay' else None,profile)):
                stream.append(Observation(a0+.0137+i/rate+j*.0001,cid,data))
    detector=RuntimeDetector(key=KEY)
    events=[e for frame in sorted(stream,key=lambda r:r.t) for e in detector.observe(frame) if e.attack_type]
    code={'fuzzy':1,'replay':2,'spoofing':3,'flooding':4}
    for attack,b0,a0,end in plan:
        assert not [e for e in events if b0<=e.timestamp<a0]
        assert {e.attack_type for e in events if a0<=e.timestamp<end}=={code[attack]}


def test_high_rate_replay_keeps_rate_evidence_without_flooding_type():
    _,events=events_for('replay','mixed-v1')
    assert any(e.reason=='FRAME_RATE' and e.attack_type==0 for e in events)


def test_flooding_suspect_is_dominant_unregistered_id():
    _,events=events_for('flooding')
    assert [(e.can_id,e.attack_type) for e in events if e.reason=='FRAME_RATE']==[(0x000,4)]


def test_replayed_original_with_fresh_auth_is_replay_not_spoofing():
    old=BMS[:3]+b'\x01'+BMS[4:]
    d=RuntimeDetector(key=KEY)
    d.observe(Observation(0,0x100,old));d.observe(Observation(.001,0x102,auth(1,old)))
    d.observe(Observation(.1,0x100,BMS));d.observe(Observation(.1005,0x100,old))
    events=d.observe(Observation(.101,0x102,auth(2,BMS)))
    assert [(e.reason,e.attack_type) for e in events if e.attack_type]==[('MAC_FAIL',2)]
    d.observe(Observation(.2,0x100,bytes([20])+BMS[1:]))
    forged=d.observe(Observation(.201,0x102,auth(3,BMS)))
    assert [(e.reason,e.attack_type) for e in forged if e.attack_type]==[('MAC_FAIL',3)]


def test_forward_counter_jump_is_not_attributed_to_replay():
    d=RuntimeDetector(key=KEY)
    d.observe(Observation(0,0x100,BMS));d.observe(Observation(.001,0x102,auth(1)))
    d.observe(Observation(.1,0x100,BMS))
    events=d.observe(Observation(.101,0x102,auth(500)))
    assert any(e.reason=='COUNTER_WINDOW' and e.attack_type==0 for e in events)


def test_single_unknown_and_short_period_remain_logged_without_false_attribution():
    detector=RuntimeDetector()
    assert detector.observe(Observation(0,0x555,BMS))[0].attack_type==0
    detector.observe(Observation(.1,0x100,BMS))
    events=detector.observe(Observation(.11,0x100,BMS))
    assert any(e.reason=='PERIOD_TOO_SHORT' and e.attack_type==0 for e in events)


def test_unknown_diversity_expires():
    d=RuntimeDetector()
    for t,cid in [(0,0x500),(.1,0x501),(1.2,0x502)]:
        assert not any(e.attack_type==1 for e in d.observe(Observation(t,cid,BMS)))


def test_fuzzy_profile_avoids_valid_message_and_alert_ids():
    rng=random.Random(1)
    for i in range(5000):
        cid,data=injection_frames('fuzzy',rng,i,None,'isolated-v1')[0]
        assert cid not in (0x100,0x101,0x102,0x103,0x200) and len(data)==8
