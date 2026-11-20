"""N07 measurement counts/times, unchanged decisions and partial lifetimes."""
from dataclasses import asdict
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from security.ids import resource_metrics as resources
from security.ids import runtime
from security.ids.runtime_detector import Config, Observation, RuntimeDetector


class Clock:
    def __init__(self, step=100):self.now=0;self.step=step
    def __call__(self):self.now+=self.step;return self.now


def measured(**kwargs):
    result=resources.RuntimeMetrics('fixture','legacy-v1','replay',clock=Clock(),cpu_clock=Clock(10),
                                    memory=lambda:{'rss_bytes':1234},**kwargs)
    result.start({'storage':'disabled'})
    return result


def test_duration_is_bounded_and_preserves_all_bucket_edges():
    value=resources.Duration()
    inputs=[0]+list(value.upper_ns)+[value.upper_ns[-1]+1]
    for elapsed in inputs:value.add(elapsed)
    report=value.report()
    assert report['calls']==len(inputs) and report['total_ns']==sum(inputs)
    assert sum(report['histogram_counts'])==len(inputs)
    assert report['histogram_counts']==[2,1,1,1,1,1,1,1]
    for _ in range(10000):value.add(10,True)
    assert len(value.buckets)==8 and value.report()['failed_calls']==10000
    assert value.report()['maximum_ns']==1_000_000_001
    with pytest.raises(ValueError):value.add(-1)
    empty=resources.Duration().report()
    assert empty['mean_ns'] is None and empty['minimum_ns'] is None


def test_exact_stage_times_and_cpu_denominators_are_host_time_only():
    metrics=measured()
    with metrics.stage('feature_extraction'):pass
    summary=metrics.report('COMPLETE',final=True)
    assert summary['durations']['feature_extraction']['total_ns']==100
    assert summary['elapsed_s']==300/1e9
    assert summary['cpu_process_s']==10/1e9
    assert summary['cpu_percent_one_core']==pytest.approx(10/300*100)
    assert summary['model_artifact']['storage']=='disabled'
    assert summary['source_clock']['used_as_host_elapsed'] is False
    assert summary['loss']['observed_socket_drops'] is None
    assert summary['loss']['receive_coverage_known'] is False
    json.dumps(summary,allow_nan=False)


def core(events):
    return [(event.timestamp,event.can_id,event.reason,event.attack_type,event.anomaly_score,event.result,
             event.alert_payload(123)) for event in events]


@pytest.mark.parametrize('score',[-.25,.25])
def test_real_detector_feature_model_calls_and_event_bytes_unchanged(score):
    class Model:
        def __init__(self):self.calls=[]
        def anomaly(self,v):self.calls.append(('anomaly',tuple(v)));return score
        def wire_score(self,v):self.calls.append(('wire',tuple(v)));return 71
    first_model,second_model=Model(),Model()
    plain=RuntimeDetector(model=first_model)
    metrics=measured();instrumented=RuntimeDetector(model=second_model);instrumented.metrics=metrics
    plain_events=[];measured_events=[]
    for frame,now in ((Observation(0,0x100,bytes.fromhex('96be1068ffec4100')),0),
                      (Observation(.9,0x555,bytes(8)),.9),(None,1.0),(None,2.1)):
        plain_events+=plain.observe(frame) if frame else plain.tick(now)
        measured_events+=metrics.process(instrumented,frame,now)
    assert core(plain_events)==core(measured_events)
    assert first_model.calls==second_model.calls
    report=metrics.report('COMPLETE',final=True);counts=report['counts'];stages=report['durations']
    assert counts['input_frames']==counts['completed_frames']==2
    assert counts['input_ticks']==counts['completed_ticks']==2
    assert counts['model_evaluations']==1 and counts['model_skipped']==1
    assert stages['feature_extraction']['calls']==stages['model_anomaly']['calls']==1
    assert stages['model_wire_score']['calls']==int(score>0)
    assert stages['detector_frame']['calls']==2 and stages['detector_tick']['calls']==2
    assert report['rates']['completed_frames_per_host_second']==2/report['elapsed_s']
    assert report['rates']['model_windows_per_host_second']==1/report['elapsed_s']


def test_error_stage_and_invalid_time_preserve_partial_counts_without_nan():
    metrics=measured();detector=RuntimeDetector();detector.metrics=metrics
    with pytest.raises(ValueError):metrics.process(detector,None,float('nan'))
    report=metrics.report('ERROR',final=True)
    assert report['counts']['failed_ticks']==report['counts']['invalid_input_times']==1
    assert report['counts']['completed_ticks']==0
    assert report['durations']['detector_tick']['failed_calls']==1
    assert report['source_clock']['first_input_s'] is None
    json.dumps(report,allow_nan=False)


def test_overflow_reset_and_unknown_wire_loss_are_separate():
    metrics=measured();detector=RuntimeDetector();detector.metrics=metrics
    # Fill real bounded raw feature deque; no invented transport loss.
    detector.frames.extend(Observation(0,0x555,bytes(8)) for _ in range(4096))
    metrics.process(detector,Observation(.1,0x555,bytes(8)),.1)
    assert metrics.counts['feature_buffer_evictions']==1 and len(detector.frames)==4096
    metrics.receive_status(7,reset=True)
    report=metrics.report('COMPLETE',final=True)
    assert report['counts']['receive_epoch_resets']==1
    assert report['source_clock']['epochs']==2
    assert report['loss']=={'observed_socket_drops':7,'receive_coverage_known':False,
                            'discarded_queue_on_reset':None,'wire_or_interface_loss':None}


def test_rss_units_and_unsupported_values_are_explicit(monkeypatch):
    class Usage:ru_maxrss=7
    monkeypatch.setattr('resource.getrusage',lambda _:Usage())
    with patch.object(resources.sys,'platform','darwin'):
        value=resources.memory_snapshot()
        assert value['rss_bytes'] is None and value['process_lifetime_peak_rss_bytes']==7
    with patch.object(resources.sys,'platform','linux'),patch.object(Path,'open',return_value=io.StringIO('VmRSS:\t9 kB\n')):
        value=resources.memory_snapshot()
        assert value['rss_bytes']==9*1024 and value['process_lifetime_peak_rss_bytes']==7*1024
    with patch.object(resources.sys,'platform','unsupported'):
        value=resources.memory_snapshot()
        assert value['rss_bytes'] is value['process_lifetime_peak_rss_bytes'] is None
        assert len(value['unavailable'])==2


def test_measurement_not_started_and_regressed_clock_never_looks_complete():
    clock=Clock();metrics=resources.RuntimeMetrics('fixture','legacy-v1','replay',clock=clock,cpu_clock=Clock(1),memory=lambda:{})
    assert metrics.report('COMPLETE',final=True)['status']=='NOT_STARTED'
    metrics.start({'storage':'disabled'})
    clock.now=-1000
    report=metrics.report('COMPLETE',final=True)
    assert report['status']=='INVALID_CLOCK' and report['elapsed_s'] is None
    assert report['rates']['completed_frames_per_host_second'] is None


def test_opt_in_cli_and_parser_failure_write_partial_summary(tmp_path):
    source=tmp_path/'frames.jsonl';source.write_text(json.dumps({'t':0,'can_id':0x555,'data':'00'*8})+'\n'+json.dumps({'tick':1.0})+'\n')
    for enabled in (False,True):
        log=tmp_path/('measured.jsonl' if enabled else 'plain.jsonl')
        args=['--replay',str(source),'--rules-only','--run-id','metric-fixture','--log',str(log)]
        if enabled:args+=['--measure-resources']
        assert runtime.main(args)==0
        rows=[json.loads(line) for line in log.read_text().splitlines()]
        summaries=[r for r in rows if r['result']=='RESOURCE_SUMMARY']
        assert len(summaries)==int(enabled)
        if enabled:
            assert summaries[0]['status']=='COMPLETE' and summaries[0]['counts']['completed_frames']==1
            assert summaries[0]['counts']['completed_ticks']==1
            assert summaries[0]['run_id']=='metric-fixture'
    source.write_text(source.read_text()+'{broken}\n')
    log=tmp_path/'failed.jsonl'
    assert runtime.main(['--replay',str(source),'--rules-only','--measure-resources','--log',str(log)])==2
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert rows[-1]['result']=='RESOURCE_SUMMARY' and rows[-1]['status']=='ERROR'
    assert rows[-1]['counts']['completed_frames']==1


def test_sigterm_measured_subprocess_keeps_partial_summary_and_restores_handler(tmp_path):
    # Real OS signal; a child that opts in. No CAN, socket, key or remote host.
    log=tmp_path/'signal.jsonl';ready=tmp_path/'ready'
    script='''import json,time,sys
from pathlib import Path
from security.ids.resource_metrics import measured_run,MeasurementTerminated
try:
 with Path(sys.argv[1]).open('x') as output:
  with measured_run(True,output,'signal-fixture','legacy-v1','replay') as metrics:
   metrics.start({'storage':'disabled'})
   Path(sys.argv[2]).write_text('ready')
   time.sleep(20)
except MeasurementTerminated:sys.exit(143)
'''
    before=signal.getsignal(signal.SIGTERM)
    child=subprocess.Popen([sys.executable,'-c',script,str(log),str(ready)])
    try:
        deadline=time.monotonic()+5
        while not ready.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert ready.exists()
        child.terminate();assert child.wait(timeout=3)==143
    finally:
        if child.poll() is None:child.kill();child.wait()
    rows=[json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows)==1 and rows[0]['status']=='INTERRUPTED' and rows[0]['final'] is True
    assert signal.getsignal(signal.SIGTERM)==before


def test_disabled_measurement_does_not_change_signal_handlers():
    before=signal.getsignal(signal.SIGTERM);output=io.StringIO()
    with resources.measured_run(False,output,'fixture','legacy-v1','replay') as metrics:
        assert metrics is None and signal.getsignal(signal.SIGTERM)==before
    assert output.getvalue()==''
