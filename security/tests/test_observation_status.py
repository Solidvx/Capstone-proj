import uuid
import pytest
from security.can_diagnostic import valid_body
from security.ids.observation_status import ObservationStatus


def update(source, start=0, **changes):
    args = dict(start_ms=start, end_ms=start+1000, frames=20, dropped=0,
                condition_mask=0)
    args.update(changes)
    return source.update(**args)


def test_wire_identity_and_continuity():
    identity=uuid.UUID('00000000-0000-4000-8000-000000000001')
    source=ObservationStatus(identity)
    body, state=update(source, condition_mask=1)
    assert valid_body(0x302, 7, body) and body[:16] == identity.bytes
    assert body[16:20] == bytes((1,0,0,0))
    assert int.from_bytes(body[20:24], 'big') == 1
    assert body[48:52] == bytes((1,0,3,0))
    body,state=update(source,1000,dropped=2)
    assert body[16:18] == bytes((2,1)) and state.healthy_span_ms == 0
    body,state=update(source,2000,frames=0)
    assert body[16:18] == bytes((2,2)) and state.ended_mask == 0


@pytest.mark.parametrize('change',[dict(frames=-1),dict(dropped=0xFFFFFFFF),dict(reason=7)])
def test_bad_sample_does_not_consume_tick(change):
    source=ObservationStatus()
    with pytest.raises(ValueError):update(source,**change)
    assert source.tick == 0
    assert update(source)[1].healthy_span_ms == 1000


def test_tick_exhaustion_never_wraps():
    source=ObservationStatus(); source.tick=0xFFFFFFFF
    with pytest.raises(OverflowError):update(source)
