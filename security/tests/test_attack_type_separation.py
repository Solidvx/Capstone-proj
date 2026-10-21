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


def test_high_rate_replay_keeps_compound_evidence():
    codes,_=events_for('replay','mixed-v1')
    assert {2,4} <= codes


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
