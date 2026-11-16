"""Actual private pipe framing and loss accounting; no CAN/SSH/key."""
import errno
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def module(monkeypatch):
    scripts=ROOT/'adaptive_ecu/scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('tx_capture_supervisor',scripts/'supervise_ecu.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def attempt():
    return {'result':'ECU_CAN_TX','schema':'ecu-can-tx-v1','instance_id':'0102030405064708890a0b0c0d0e0f10',
            'sequence':1,'started_ns':100,'ended_ns':200,'can_id':0x100,'dlc':8,'data':'96be1068ffec4100',
            'counter':None,'syscall_attempted':True,'returned_bytes':16,'error_number':0,
            'kernel_accepted':True,'records_dropped':0}


def end(attempts=1,written=1,dropped=0):
    return {'result':'ECU_CAN_TX_END','schema':'ecu-can-tx-v1','instance_id':attempt()['instance_id'],
            'attempts':attempts,'records_written':written,'records_dropped':dropped,'ended_ns':300}


def feed(capture,row):
    raw=(json.dumps(row,separators=(',',':'))+'\n').encode()
    assert len(raw)<512
    os.write(capture.writer,raw)
    capture.poll()


def test_success_auth_failure_counters_and_actual_eof(module):
    rows=[];capture=module.TxTraceCapture(rows.append);capture.pid=123
    feed(capture,attempt())
    auth=attempt();auth.update(sequence=2,can_id=0x102,data='0102030400000000',counter=0,
                               returned_bytes=-1,error_number=105,kernel_accepted=False)
    feed(capture,auth);feed(capture,end(2,2,0));capture.handed_off();capture.close()
    assert [r['result'] for r in rows]==['ECU_CAN_TX','ECU_CAN_TX','ECU_CAN_TX_END','ECU_CAN_TX_CAPTURE_END']
    assert rows[-1]['status']=='COMPLETE' and rows[-1]['final_record_available'] is True
    assert all(r['ecu_pid']==123 for r in rows)
    assert rows[1]['counter']==0 and rows[1]['kernel_accepted'] is False


def test_explicit_lost_records_are_kept_not_filled_by_arrival_or_retry(module):
    rows=[];capture=module.TxTraceCapture(rows.append)
    row=attempt();row.update(sequence=3,records_dropped=2)
    feed(capture,row);feed(capture,end(4,1,3));capture.handed_off();capture.close()
    assert rows[-1]['status']=='COMPLETE'  # complete trace stream can contain explicit loss
    assert rows[0]['sequence']==3 and rows[1]['records_dropped']==3
    assert len([r for r in rows if r['result']=='ECU_CAN_TX'])==1


@pytest.mark.parametrize('change',[
    {'sequence':2},{'kernel_accepted':False},{'ended_ns':99},{'error_number':True},
    {'can_id':0x102,'counter':9},{'data':'zz'},{'syscall_attempted':False},
    {'returned_bytes':-1,'kernel_accepted':False,'error_number':0},
    {'unexpected_field':'public-dummy-do-not-forward'},
])
def test_malformed_trace_isolated_and_never_complete(module,change):
    rows=[];capture=module.TxTraceCapture(rows.append)
    row=attempt();row.update(change)
    feed(capture,row);capture.handed_off();capture.close()
    assert len(rows)==1 and rows[0]['result']=='ECU_CAN_TX_CAPTURE_END'
    assert rows[0]['status']=='INCOMPLETE' and rows[0]['error']
    assert 'public-dummy-do-not-forward' not in json.dumps(rows)


def test_partial_line_missing_end_mixed_instance_and_end_denominator(module):
    for variant in ('partial','missing-end','mixed-instance','bad-end','after-end','oversized'):
        rows=[];capture=module.TxTraceCapture(rows.append)
        try:
            feed(capture,attempt())
            if variant=='partial':os.write(capture.writer,b'{"result":');capture.poll()
            elif variant=='mixed-instance':
                row=end();row['instance_id']='0'*32;feed(capture,row)
            elif variant=='bad-end':feed(capture,end(9,1,0))
            elif variant=='after-end':feed(capture,end());feed(capture,attempt())
            elif variant=='oversized':os.write(capture.writer,b'x'*512);capture.poll()
            capture.handed_off();capture.close()
            assert rows[-1]['status']=='INCOMPLETE',variant
        finally:
            if capture.reader>=0:os.close(capture.reader)
            if capture.writer>=0:os.close(capture.writer)


def test_short_syscall_and_precheck_are_distinct_from_kernel_acceptance(module):
    rows=[];capture=module.TxTraceCapture(rows.append)
    row=attempt();row.update(returned_bytes=8,kernel_accepted=False)
    feed(capture,row)
    row=attempt();row.update(sequence=2,returned_bytes=-1,error_number=9,
                             syscall_attempted=False,kernel_accepted=False)
    feed(capture,row);feed(capture,end(2,2));capture.handed_off();capture.close()
    assert rows[-1]['status']=='COMPLETE'
    assert rows[0]['returned_bytes']==8 and rows[0]['error_number']==0
    assert rows[1]['syscall_attempted'] is False


@pytest.mark.parametrize('error_number',[errno.EIO,errno.EBADF])
def test_read_error_closes_only_trace_and_reports_incomplete(module,monkeypatch,error_number):
    rows=[];capture=module.TxTraceCapture(rows.append)
    original_read=os.read
    def fail_trace(fd,size):
        if fd==capture.reader:raise OSError(error_number,'test-only read fault')
        return original_read(fd,size)
    with monkeypatch.context() as patch:
        patch.setattr(os,'read',fail_trace)
        assert capture.poll() is False and capture.reader==-1
    capture.handed_off();capture.close()
    assert rows[-1]['status']=='INCOMPLETE'
    assert rows[-1]['error']=='trace read failed: errno='+str(error_number)
    # A separate owned stream can still complete; no shared health failure.
    other=module.TxTraceCapture(rows.append)
    feed(other,attempt());feed(other,end());other.handed_off();other.close()
    assert rows[-1]['status']=='COMPLETE'


def test_interrupted_read_can_resume_same_trace(module,monkeypatch):
    rows=[];capture=module.TxTraceCapture(rows.append)
    with monkeypatch.context() as patch:
        def interrupted(*_):raise InterruptedError()
        patch.setattr(os,'read',interrupted)
        assert capture.poll() is False and capture.reader>=0 and capture.error is None
    feed(capture,attempt());feed(capture,end());capture.handed_off();capture.close()
    assert rows[-1]['status']=='COMPLETE'


def test_already_closed_reader_is_incomplete_without_cleanup_exception(module):
    rows=[];capture=module.TxTraceCapture(rows.append)
    os.close(capture.reader)
    assert capture.poll() is False and capture.reader==-1
    capture.handed_off();capture.close()
    assert rows[-1]['status']=='INCOMPLETE'
    assert rows[-1]['error']=='trace read failed: errno='+str(errno.EBADF)
