import pytest
from security.ids.observation_status import ObservationStatus
from security.ids.incident_status import IncidentStatus


def test_identity_survives_gap_and_changes_only_after_confirmed_end():
    obs=ObservationStatus(); ids=IncidentStatus()
    def step(t,mask=0,drop=0):
        body,state=obs.update(start_ms=t,end_ms=t+1000,frames=20,dropped=drop,condition_mask=mask)
        return ids.update(body,state)
    first=step(0,3)
    assert len(first)==2 and first[0][16:32]!=first[1][16:32]
    unknown=step(1000,drop=1)
    assert all(row[33]==3 for row in unknown)
    assert unknown[0][16:32]==first[0][16:32]
    for t in range(2000,6000,1000):assert step(t)==[]
    ended=step(6000)
    assert len(ended)==2 and all(row[33]==2 for row in ended)
    assert ended[0][16:32]==first[0][16:32]
    restarted=step(7000,1)
    assert restarted[0][16:32]!=first[0][16:32]
    body,state=obs.update(start_ms=8000,end_ms=9000,frames=20,dropped=0,condition_mask=1)
    ids.update(body,state)
    with pytest.raises(ValueError):ids.update(body,state)
