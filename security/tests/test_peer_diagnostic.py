import fcntl
import os
import json
from contextlib import contextmanager

import pytest
from security.can_session import context_id
from security.ids.peer_diagnostic import PACKET,PeerDiagnostics
from security.tests.diagnostic_fixtures import fixtures,uuid_bytes

CTX,_,FIXTURES=fixtures()
BODY=next(body for name,_,_,_,body in FIXTURES if name=='rejection')
SESSION=context_id(CTX)


class Context:
    generation=2;boundary_ns=1;open=True
    def ready(self,now):return self.open
    def fingerprint(self):return SESSION.hex()


def packet(sequence=1,published=12_000_000,verified=11_000_000,generation=2,session=SESSION,drops=0,body=BODY):
    return PACKET.pack(b'CPR1',generation,published,10_000_000,verified,sequence,session,drops,body)


@contextmanager
def pipe():
    reader,writer=os.pipe()
    for fd in (reader,writer):fcntl.fcntl(fd,fcntl.F_SETFL,fcntl.fcntl(fd,fcntl.F_GETFL)|os.O_NONBLOCK)
    source=PeerDiagnostics(reader,Context())
    try:yield source,writer
    finally:
        source.close();os.close(writer)


def test_real_pipe_fragmentation_no_new_attack_label_or_if_feature():
    with pipe() as (source,writer):
        raw=packet();os.write(writer,raw[:50]);assert source.poll(12_000_000)==[]
        os.write(writer,raw[50:]);record=source.poll(13_000_000)[0]
        assert record['result']=='PEER_REJECTION_CONSUMED' and record['body_hex']==BODY.hex()
        assert record['reason']==7 and record['mac_verified'] and record['treatment']==1
        assert record['recent_1s_reason_counts']=={7:1} and record['recent_1s_count_complete']
        assert record['diagnostic_only'] and not record['attack_type_inferred'] and not record['if_features_changed']
        assert not record['source_event_age_known']


def test_local_old_sequence_and_uuid_do_not_increase_counts():
    with pipe() as (source,_):
        assert source.consume(packet(),13_000_000)['result']=='PEER_REJECTION_CONSUMED'
        assert source.consume(packet(),13_000_000)['reason']=='OLD_OR_DUPLICATE_SEQUENCE'
        assert source.consume(packet(sequence=2),13_000_000)['reason']=='DUPLICATE_REJECTION_ID'
        assert len(source.recent)==1


@pytest.mark.parametrize('damage',['generation','session','closed_context','boundary'])
def test_unconfirmed_context_is_not_consumed(damage):
    with pipe() as (source,_):
        options={}
        if damage=='generation':options['generation']=3
        elif damage=='session':options['session']=b'x'*16
        elif damage=='closed_context':source.context.open=False
        else:source.context.boundary_ns=15_000_000
        result=source.consume(packet(**options),20_000_000)
        assert result['reason']=='CONTEXT_UNCONFIRMED' and not source.recent


def test_strict_three_second_delivery_boundary_and_old_window():
    with pipe() as (source,_):
        assert source.consume(packet(),3_011_000_000)['reason']=='STALE_LOCAL_DELIVERY'
    with pipe() as (source,_):
        result=source.consume(packet(),2_000_000_000)
        assert result['result']=='PEER_REJECTION_CONSUMED' and result['recent_1s_reason_counts']=={}


def test_explicit_producer_drops_are_preserved_and_counts_marked_incomplete():
    with pipe() as (source,_):
        result=source.consume(packet(drops=4),13_000_000)
        assert result['producer_drops']==result['producer_drops_total']==4
        assert not result['recent_1s_count_complete']
        with pytest.raises(ValueError,match='regressed'):source.consume(packet(sequence=2,drops=3),14_000_000)


def test_bounded_recent_aggregation_does_not_hide_truncation():
    with pipe() as (source,_):
        for k in range(257):
            body=BODY[:16]+uuid_bytes(k%255)+BODY[32:]
            # Use unique UUIDs even after the helper's repeated-byte range.
            body=bytearray(body);body[16:20]=k.to_bytes(4,'big')
            result=source.consume(packet(sequence=k,body=bytes(body)),13_000_000)
        assert len(source.ids)==len(source.recent)==256 and len(source.seen)==256
        assert result['recent_1s_reason_counts']=={7:256} and not result['recent_1s_count_complete']


def test_bad_packet_disables_only_diagnostic_channel_and_empty_pipe_is_nonblocking():
    with pipe() as (source,writer):
        assert source.poll(13_000_000)==[]
        bad=bytearray(packet());bad[0]=0;os.write(writer,bad)
        record=source.poll(14_000_000)[0]
        assert record['result']=='PEER_DIAGNOSTIC_UNAVAILABLE' and record['raw_if_continues']
        assert source.failed and source.poll(15_000_000)==[]


def test_reader_requires_correct_fd_type_direction_and_mode(tmp_path):
    fd=os.open(tmp_path/'regular',os.O_RDONLY|os.O_CREAT,0o600)
    try:
        with pytest.raises(ValueError):PeerDiagnostics(fd,Context())
    finally:os.close(fd)
    with pipe() as (_,writer):
        with pytest.raises(ValueError):PeerDiagnostics(writer,Context())


@pytest.mark.parametrize('damage',['future','body','clock'])
def test_impossible_local_packets_and_clock_are_isolated(damage):
    with pipe() as (source,writer):
        raw=packet(published=14_000_000) if damage=='future' else packet()
        if damage=='body':raw=bytearray(raw);raw[64+32]=0
        os.write(writer,raw)
        if damage=='clock':source.poll(15_000_000);result=source.poll(14_000_000)[0]
        else:result=source.poll(13_000_000)[0]
        assert result['result']=='PEER_DIAGNOSTIC_UNAVAILABLE' and result['raw_if_continues']


def test_eof_disables_only_peer_and_generation_change_allows_new_sequence():
    with pipe() as (source,writer):
        assert source.consume(packet(),13_000_000)['result']=='PEER_REJECTION_CONSUMED'
        source.context.generation=3
        assert source.consume(packet(generation=3,sequence=0),14_000_000)['result']=='PEER_REJECTION_CONSUMED'
    reader,writer=os.pipe()
    fcntl.fcntl(reader,fcntl.F_SETFL,fcntl.fcntl(reader,fcntl.F_GETFL)|os.O_NONBLOCK)
    source=PeerDiagnostics(reader,Context());os.close(writer)
    try:
        result=source.poll(15_000_000)[0]
        assert result['result']=='PEER_DIAGNOSTIC_UNAVAILABLE'
    finally:source.close()


def test_live_runtime_keeps_processing_raw_after_poisoned_peer_packet(tmp_path):
    from unittest.mock import Mock,patch
    from security.ids.runtime import main
    from security.ids.runtime_detector import Observation
    class LiveContext(Context):
        def __init__(self,*args,**kwargs):pass
        def poll(self,now):return False
    bus=Mock(start_time=0.,clock_offset_ns=0,rx_dropped=0)
    bus.receive.side_effect=[Observation(.01,0x555,bytes(8),8),Observation(.02,0x556,bytes(8),8)]
    reader,writer=os.pipe()
    fcntl.fcntl(reader,fcntl.F_SETFL,fcntl.fcntl(reader,fcntl.F_GETFL)|os.O_NONBLOCK)
    bad=bytearray(packet());bad[0]=0;os.write(writer,bad)
    key=tmp_path/'public-dummy.key';key.write_bytes(bytes(range(32)));log=tmp_path/'events.jsonl'
    try:
        with patch('security.ids.session_context.ContextSource',LiveContext), \
             patch('security.ids.runtime.OrderedSocketCan',return_value=bus), \
             patch('security.ids.runtime.time.monotonic',side_effect=lambda:2. if bus.receive.call_count>=2 else 0.), \
             patch('security.ids.runtime.time.monotonic_ns',return_value=20_000_000):
            code=main(['--interface','test-only','--protocol','session-v2','--rules-only',
                '--session-context-fd','1000','--peer-rejection-fd',str(reader),'--secoc-key',str(key),
                '--log',str(log),'--duration','1'])
    finally:
        os.close(writer)
        try:os.close(reader)
        except OSError:pass # runtime owns and closes the supplied read descriptor.
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert code==0 and bus.receive.call_count==2
    assert sum(row.get('reason')=='UNKNOWN_ID' for row in rows)==2
    assert sum(row.get('result')=='PEER_DIAGNOSTIC_UNAVAILABLE' for row in rows)==1
    assert rows[-1]['result']=='END'


def test_valid_reverse_order_window_is_not_discarded_as_duplicate():
    with pipe() as (source,_):
        assert source.consume(packet(sequence=100),13_000_000)['result']=='PEER_REJECTION_CONSUMED'
        different=BODY[:16]+uuid_bytes(0x56)+BODY[32:]
        assert source.consume(packet(sequence=37,body=different),14_000_000)['result']=='PEER_REJECTION_CONSUMED'
        old=BODY[:16]+uuid_bytes(0x57)+BODY[32:]
        assert source.consume(packet(sequence=36,body=old),15_000_000)['reason']=='OLD_OR_DUPLICATE_SEQUENCE'
        assert len(source.recent)==2 and len(source.sequences)==2


def test_conflicting_same_record_id_is_visible_and_counts_uncertain():
    with pipe() as (source,_):
        source.consume(packet(),13_000_000)
        changed=bytearray(BODY);changed[64]^=1
        result=source.consume(packet(sequence=2,body=bytes(changed)),14_000_000)
        assert result['reason']=='CONFLICTING_REJECTION_ID' and result['previous_body_hex']==BODY.hex()
        assert result['body_hex']==changed.hex() and not result['recent_1s_count_complete']
        assert len(source.recent)==1


def test_batch_keeps_consumed_records_before_fault_and_has_eight_record_budget():
    with pipe() as (source,writer):
        bad=bytearray(packet(sequence=2));bad[0]=0
        os.write(writer,packet()+bad)
        result=source.poll(13_000_000)
        assert [r['result'] for r in result]==['PEER_REJECTION_CONSUMED','PEER_DIAGNOSTIC_UNAVAILABLE']
        assert result[-1]['unconfirmed_buffer_bytes']==PACKET.size
    with pipe() as (source,writer):
        for k in range(9):
            body=BODY[:16]+uuid_bytes(k)+BODY[32:];os.write(writer,packet(sequence=k,body=body))
        assert len(source.poll(13_000_000))==8
        assert len(source.poll(14_000_000))==1
