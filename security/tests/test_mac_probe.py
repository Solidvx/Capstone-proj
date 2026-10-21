import pytest
from security.experiments.mac_rejection_probe import forge
from security.experiments.score_mac_probe import score


def evidence():
    probe=[];ivi=[]
    for i in range(1,31):
        raw,auth=forge(bytes.fromhex('99c80f3cffec4100'),bytes(4)+i.to_bytes(4,'big'))
        probe += [dict(result='PREPARED',trial=i,raw=raw.hex(),auth=auth.hex()),dict(result='TX',trial=i,can_id=256,data=raw.hex()),dict(result='TX',trial=i,can_id=258,data=auth.hex())]
        ivi.append(dict(result='FRAME',can_id=258,data=auth.hex(),source_data=raw.hex(),process_result=3,message='reason=MAC_FAIL can_id=256'))
    return probe+[dict(result='COMPLETE',rx_dropped=0)],ivi


def test_all_mac_rejections():
    p,i=evidence();r=score(p,i)
    assert r['complete_coverage'] and r['counts']=={'MAC_REJECTED':30}


def test_missing_duplicate_wrong_source_and_other_rejection():
    p,i=evidence();i.pop();i.append(i[0].copy());i[1]['source_data']='wrong';i[2]['message']='reason=COUNTER_WINDOW';i[3]['process_result']=2
    r=score(p,i)
    assert r['counts']=={'AMBIGUOUS':2,'OTHER_REJECTION':1,'PUBLISHED':1,'MAC_REJECTED':25,'UNOBSERVED':1}
    assert not r['complete_coverage']


def test_incomplete_transmission_refused():
    p,i=evidence();p.pop(1)
    with pytest.raises(ValueError):score(p,i)
