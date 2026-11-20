import pytest
from security.ids.observation_continuity import ObservationContinuity


def sample(tracker, start, mask=0, **changes):
    args = dict(start_ms=start, end_ms=start+1000, condition_mask=mask,
                frames=20, dropped=0, healthy=True)
    args.update(changes)
    return tracker.update(**args)


def test_types_end_independently_after_measured_quiet():
    tracker = ObservationContinuity()
    sample(tracker, 0, 3)
    for start in range(1000, 5000, 1000):
        assert sample(tracker, start, 2).ended_mask == 0
    assert sample(tracker, 5000, 2).ended_mask == 1
    for start in range(6000, 10000, 1000):
        assert sample(tracker, start).ended_mask == 0
    assert sample(tracker, 10000).ended_mask == 2
    assert sample(tracker, 11000).ended_mask == 0


@pytest.mark.parametrize('changes', [dict(frames=0), dict(dropped=1), dict(healthy=False)])
def test_uncertainty_does_not_end_incident(changes):
    tracker = ObservationContinuity()
    sample(tracker, 0, 8)
    for start in range(1000, 5000, 1000):
        sample(tracker, start)
    result = sample(tracker, 5000, **changes)
    assert result.healthy_span_ms == 0 and result.ended_mask == 0
    assert result.quiet_span_ms == (0, 0, 0, 0)
    for start in range(6000, 10000, 1000):
        assert sample(tracker, start).ended_mask == 0
    assert sample(tracker, 10000).ended_mask == 8


def test_gap_and_repeated_windows_cannot_manufacture_quiet():
    tracker = ObservationContinuity()
    sample(tracker, 0, 4)
    sample(tracker, 1000)
    result = sample(tracker, 20000)
    assert result.quiet_span_ms[2] == 1000 and result.ended_mask == 0
    with pytest.raises(ValueError):
        sample(tracker, 20000)
    assert sample(tracker, 21000).quiet_span_ms[2] == 2000


def test_reappearance_resets_only_its_quiet_interval():
    tracker = ObservationContinuity()
    sample(tracker, 0, 3)
    sample(tracker, 1000)
    assert sample(tracker, 2000, 1).quiet_span_ms[:2] == (0, 2000)
