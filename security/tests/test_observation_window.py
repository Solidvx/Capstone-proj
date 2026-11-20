from types import SimpleNamespace
from security.ids.observation_window import ObservationWindow


def test_live_window_keeps_process_relative_time_and_measured_drops():
    window=ObservationWindow(900000)
    assert window.observe(900500,frame_present=True,events=[SimpleNamespace(attack_type=4)],total_drops=0) is None
    body,state=window.observe(901000,frame_present=True,events=[],total_drops=0)
    assert int.from_bytes(body[24:32],'big') == 1000
    assert int.from_bytes(body[36:40],'big') == 2
    assert body[48] == 8 and body[16] == 1
    body,state=window.observe(902000,frame_present=True,events=[],total_drops=3)
    assert body[16:18] == bytes((2,1))
    assert int.from_bytes(body[40:44],'big') == 3
    body,state=window.observe(905000,frame_present=True,events=[],total_drops=3)
    assert body[16:18] == bytes((2,2)) and state.ended_mask == 0


def test_backlogged_kernel_frames_do_not_claim_healthy_live_observation():
    window=ObservationWindow(0)
    assert window.observe(500,frame_present=True,events=[],total_drops=0,
                          processed_ms=10000) is None
    body,state=window.observe(1000,frame_present=True,events=[],total_drops=0,
                              processed_ms=10000)
    assert body[16:18] == bytes((2,2))
    assert state.healthy_span_ms == 0 and state.ended_mask == 0
    body,state=window.observe(2000,frame_present=True,events=[],total_drops=0,
                              processed_ms=2001)
    assert body[16] == 1 and state.healthy_span_ms == 1000
