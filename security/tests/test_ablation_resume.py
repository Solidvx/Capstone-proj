import errno
import io
import json
import pytest
from security.experiments.live_ablation import send_bounded, main


def exercise(errors, deadline=1.0):
    now=[0.0]; calls=[]; log=io.StringIO()
    class Bus:
        def send(self,cid,payload):
            calls.append((now[0],cid,payload))
            if errors:
                code=errors.pop(0)
                if code:raise OSError(code,'test')
    def sleep(delay):now[0]+=delay
    result=send_bounded(Bus(),0x100,b'12345678',deadline,log,lambda:now[0],sleep)
    return result,calls,[json.loads(x) for x in log.getvalue().splitlines()]


def test_transient_failure_retries_identical_payload_and_preserves_error():
    ok,calls,log=exercise([errno.ENOBUFS,0])
    assert ok and len(calls)==2
    assert calls[0][1:]==calls[1][1:] and calls[1][0]==pytest.approx(.001)
    assert log[0]['errno']==errno.ENOBUFS and log[0]['retry_planned']
    assert log[1]['tx_retries']==1


def test_persistent_pressure_is_bounded_and_fails():
    ok,calls,log=exercise([errno.ENOBUFS]*20)
    assert not ok and len(calls)<=6 and calls[-1][0]<=.005
    assert not log[-1]['retry_planned']


def test_permanent_error_never_retried():
    ok,calls,log=exercise([errno.ENETDOWN]*20)
    assert not ok and len(calls)==1 and not log[0]['retry_planned']


def test_no_retry_past_attack_deadline():
    ok,calls,log=exercise([errno.ENOBUFS]*20,deadline=.0005)
    assert not ok and len(calls)==1


@pytest.mark.parametrize('extra',[
    ['--start-trial','7'],
    ['--start-trial','7','--previous-run-id','old','--trials','95'],
    ['--start-trial','0'],
])
def test_invalid_resume_range_rejected_before_opening_bus(extra,tmp_path):
    with pytest.raises(SystemExit) as error:
        main(['--channel','vcan0','--environment','vcan','--config','1',
              '--ecu','unused','--out',str(tmp_path/'new'),'--run-id','new']+extra)
    assert error.value.code==2
    assert not (tmp_path/'new').exists()


def test_scheduler_oversleep_does_not_send_after_retry_budget():
    now = [0.0]
    calls = []
    class Bus:
        def send(self, cid, payload):
            calls.append(now[0])
            raise OSError(errno.ENOBUFS, 'test')
    def sleep(delay):
        now[0] += .010
    assert not send_bounded(Bus(), 256, b'12345678', 1., io.StringIO(),
                            lambda: now[0], sleep)
    assert calls == [0.0]


def test_expired_deadline_is_logged_without_syscall_or_tx_failure():
    ok, calls, log = exercise([], deadline=0.)
    assert ok is None and calls == []
    assert log[0]['tx_skipped'] == 'ATTACK_DEADLINE'


def test_continue_invalid_policy_retains_rows_and_visits_next_index():
    from security.experiments.live_ablation import enforce_attempt_policy
    ledger = []
    for trial, status in [(21, 'INVALID'), (22, 'VALID')]:
        row = {'trial': trial, 'status': status, 'invalid_reason': 'TX_ERRORS' if trial == 21 else ''}
        ledger.append(row)
        enforce_attempt_policy(row, True)
    assert [r['trial'] for r in ledger] == [21, 22]
    assert ledger[0]['status'] == 'INVALID'
    with pytest.raises(RuntimeError):
        enforce_attempt_policy(ledger[0], False)


def test_collect_does_not_count_unattempted_deadline_frame(monkeypatch):
    import security.experiments.live_ablation as runner
    now = [0.]
    class Children:
        def check(self): pass
    class Bus:
        def receive(self, wait):
            now[0] += wait
            return None
    class Receiver:
        def poll(self, t): return []
    def expired(*args):
        now[0] = 1.
        return None
    monkeypatch.setattr(runner, 'send_bounded', expired)
    result = runner.collect(Bus(), Receiver(), .1, io.StringIO(), Children(),
                            attack='flooding', clock=lambda: now[0])
    assert result[1] == 0 and result[2] == 0
