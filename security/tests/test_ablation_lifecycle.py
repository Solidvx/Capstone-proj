import io
import json
import socket
import struct
from unittest.mock import Mock, patch
import pytest
from security.experiments.live_ablation import IdsEvidenceReader
from security.experiments.can_capture import CaptureSocket
from security.ids.runtime import main


def test_incremental_reader_keeps_partial_line_and_future_events(tmp_path):
    path = tmp_path/'ids.jsonl'
    def event(t): return json.dumps(dict(result='ANOMALY', timestamp=t, reason='UNKNOWN_ID'))+'\n'
    path.write_text(event(1)+event(3)+event(4)[:20])
    reader=IdsEvidenceReader(path)
    assert reader.count(0,2)['rule_events']==1
    offset=reader.offset
    with path.open('a') as out:out.write(event(4)[20:])
    assert reader.count(2,5)['rule_events']==2
    assert reader.offset>offset
    assert reader.count(5,6)['rule_events']==0 and not reader.pending


def test_owned_ids_outlives_duration_and_exits_after_parent_loss(tmp_path):
    bus=Mock(start_time=0, clock_offset_ns=0, idle_time=0)
    bus.receive.return_value=None
    with patch('security.ids.runtime.SocketCan',return_value=bus), patch('security.ids.runtime.os.getppid',side_effect=[123,123,123,1]), patch('security.ids.runtime.time.monotonic',side_effect=[0,0]):
        assert main(['--interface','test','--rules-only','--parent-pid','123','--duration','.001','--log',str(tmp_path/'ids')])==0
    assert bus.receive.call_count==2
    bus.close.assert_called_once()


@pytest.mark.skipif(not hasattr(socket,'MSG_CONFIRM'),reason='Linux')
def test_capture_backlog_uses_arrival_time_not_dequeue_time():
    bus=CaptureSocket.__new__(CaptureSocket)
    bus.socket=Mock();bus.dropped=0;bus.kernel_timestamps=True;bus.clock_offset_ns=-990_000_000_000
    bus.socket.recvmsg.return_value=(struct.pack('=IB3x8s',0x100,8,bytes(8)),[(socket.SOL_SOCKET,64,struct.pack('=qq',1000,0))],0,None)
    with patch('security.experiments.can_capture.select.select',return_value=([bus.socket],[],[])),patch('security.experiments.can_capture.time.monotonic',return_value=15),patch('security.experiments.can_capture.time.monotonic_ns',return_value=15_000_000_000),patch('security.experiments.can_capture.time.time_ns',return_value=1005_000_000_000):
        assert bus.receive()[0].t==10
        bus.socket.recvmsg.return_value=(struct.pack('=IB3x8s',0x100,8,bytes(8)),[],0,None)
        with pytest.raises(ValueError,match='missing kernel'):bus.receive()


def test_large_history_not_reread_for_next_window(tmp_path):
    path=tmp_path/'ids.jsonl'
    line=json.dumps(dict(result='NORMAL',timestamp=0))+'\n'
    path.write_text(line*10000)
    reader=IdsEvidenceReader(path)
    assert reader.count(0,1)['rule_events']==0
    offset=reader.offset
    with path.open('a') as out:out.write(json.dumps(dict(result='ANOMALY',timestamp=2,reason='IF_ANOMALY'))+'\n')
    assert reader.count(1,3)['if_events']==1
    assert reader.offset>offset and len(reader.pending)==1


def test_late_dequeue_does_not_count_pre_attack_bms_in_attack_window():
    from security.experiments.live_trial import Record, TrialWindows, judge_trial
    from security.experiments.live_receiver import Outcome
    payload=bytes.fromhex('96be1068ffec4100')
    records=[Record(1+i*.1,0x100,payload,False,[Outcome('PUBLISHED',0x100,original_t=1+i*.1)]) for i in range(20)]
    # These frames could be dequeued after t=5 but retain kernel arrival t=1..2.9.
    result=judge_trial(1,'flooding',records,TrialWindows(0,5,8,9,5.1),1)
    assert result['normal_seen']==0 and result['normal_delivered']==0
