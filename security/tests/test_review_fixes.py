import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from security.attack_simulator import main, capture_replay_pair
from security.can_socket import CanFrame
from security.capture_normal import capture_summary, validate_capture
from security.ids.runtime import main as ids_main
from security.experiments.run_ablation import summarize_observations, trial_seed
from security.experiments.summarize_ablation import summarize


class ReviewFixTests(unittest.TestCase):
    def test_pair_rate_limit_and_physical_run_id_are_checked_before_open(self):
        with patch('security.attack_simulator.SocketCanTransport') as transport:
            self.assertEqual(main(['--type','replay','--replay-mode','authenticated-pair',
                '--rate','2500','--channel','can0','--confirm-isolated-test-bus',
                '--run-id','rate-check','--log','/unused-test-output']),2)
            self.assertEqual(main(['--type','flooding','--channel','can0',
                '--confirm-isolated-test-bus','--log','/unused-test-output']),2)
            transport.assert_not_called()

    def test_replay_attribution_allows_receiver_socket_to_wake_first(self):
        raw='96be1068ffec4100';auth='00'*8
        tx=[{'result':'TX_ACCEPTED','can_id':0x100,'data':raw},
            {'result':'TX_ACCEPTED','can_id':0x102,'data':auth}]
        bus=[{'result':'BUS_FRAME','can_id':cid,'data':data,'timestamp_ns':str(ns)}
             for cid,data,ns in ((0x100,raw,0),(0x102,auth,2000000),
                                 (0x100,raw,1000000000),(0x102,auth,1002000000))]
        receiver=[{'result':'FRAME','can_id':cid,'data':data,'source_data':raw,
                  'timestamp_ns':str(ns),'process_result':result,'soc':75}
                  for cid,data,ns,result in ((0x100,raw,0,2),
                    (0x100,raw,999900000,2),(0x102,auth,1002100000,0))]
        result=summarize_observations(1,'replay',tx,bus,receiver,
            [{'result':'NORMAL_TX','can_id':0x100}])
        self.assertTrue(result['attack_success'])
        self.assertEqual(result['normal_delivered'],1)

    def test_transmission_error_and_interrupt_preserve_successful_count(self):
        for failure,code in ((OSError('TX queue full'),2),(KeyboardInterrupt(),130)):
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'attack.json'
                transport=Mock()
                transport.__enter__=Mock(return_value=transport)
                transport.__exit__=Mock(return_value=False)
                transport.send.side_effect=[None,failure]
                with patch('security.attack_simulator.SocketCanTransport',return_value=transport):
                    self.assertEqual(main(['--type','flooding','--duration','.01','--log',str(path)]),code)
                result=json.loads(path.read_text())
                self.assertEqual(result['sent_frames'],1)
                self.assertIsNotNone(result['first_tx_accepted_monotonic_ns'])
                journal=[json.loads(v) for v in Path(str(path)+'.journal.jsonl').read_text().splitlines()]
                self.assertEqual([v['result'] for v in journal],['START','TX_ACCEPTED','END'])

    def test_replay_pair_ignores_orphan_and_invalid_auth(self):
        bus=Mock()
        raw=bytes.fromhex('96be1068ffec4100');auth=bytes.fromhex('d0ddfc0500000000')
        bus.receive.side_effect=[CanFrame(0x102,auth),CanFrame(0x100,raw),
            CanFrame(0x102,auth,remote=True),CanFrame(0x102,auth)]
        self.assertEqual(capture_replay_pair(bus,.1),(raw,auth))

    def test_empty_gapped_and_hash_changed_normal_capture_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);capture=root/'normal.jsonl';manifest=root/'manifest.json'
            capture.write_text('')
            with self.assertRaises(ValueError):capture_summary(capture,4,{0x100,0x102})
            records=[{'t':i*.1+offset,'can_id':cid,'data':'96be1068ffec4100'}
                for i in range(40) for cid,offset in ((0x100,0),(0x102,.002))]
            capture.write_text(''.join(json.dumps(v)+'\n' for v in records))
            metadata={'schema':'ids-normal-v2','status':'COMPLETE','duration_s':4,
                'rejected_frames':0,'allowed_ids':[0x100,0x102],'accepted_frames':80,
                'capture_sha256':hashlib.sha256(capture.read_bytes()).hexdigest()}
            manifest.write_text(json.dumps(metadata))
            self.assertEqual(validate_capture(capture,manifest)['status'],'COMPLETE')
            capture.write_text(capture.read_text()+'\n')
            with self.assertRaises(ValueError):validate_capture(capture,manifest)
            records=[r for r in records if not 1<r['t']<2]
            capture.write_text(''.join(json.dumps(v)+'\n' for v in records))
            with self.assertRaises(ValueError):capture_summary(capture,4,{0x100,0x102})

    def test_live_ready_is_written_only_after_socket_opens(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ready=root/'ready.json';log=root/'ids.jsonl'
            socket=Mock(start_time=0.0, clock_offset_ns=0, idle_time=0.0)
            socket.receive.return_value=None
            with patch('security.ids.runtime.SocketCan',return_value=socket):
                self.assertEqual(ids_main(['--interface','vcan0','--rules-only','--duration','.001',
                    '--log',str(log),'--run-id','pilot','--ready-file',str(ready)]),0)
            self.assertEqual(json.loads(ready.read_text())['run_id'],'pilot')
            bad_ready=root/'bad-ready.json'
            with patch('security.ids.runtime.SocketCan',side_effect=OSError('bind failed')):
                self.assertEqual(ids_main(['--interface','vcan0','--rules-only','--log',str(root/'bad-log'),
                    '--ready-file',str(bad_ready)]),2)
            self.assertFalse(bad_ready.exists())

    def test_detection_does_not_imply_blocking_or_prevent_pollution(self):
        spoof='c8be1068ffec4100'
        tx=[{'result':'TX_ACCEPTED','can_id':0x100,'data':spoof}]
        bus=[{'result':'BUS_FRAME','can_id':0x100,'data':spoof,'timestamp_ns':'1000000000'},
             {'result':'BUS_FRAME','can_id':0x200,'data':'0396010000000000','timestamp_ns':'1100000000'}]
        receiver=[{'result':'FRAME','can_id':0x102,'data':'00'*8,'source_data':spoof,
            'timestamp_ns':'1002000000','process_result':2,'soc':100}]
        result=summarize_observations(3,'spoofing',tx,bus,receiver,[])
        self.assertTrue(result['attack_success']);self.assertTrue(result['detected'])
        self.assertFalse(result['blocked']);self.assertAlmostEqual(result['latency_s'],.1)

    def test_missing_trials_and_misdetections_have_explicit_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'settings.json').write_text('{}')
            (root/'manifest.json').write_text(json.dumps({'schema':'ablation-v1','run_id':'r','environment':'vcan',
                'settings_sha256':hashlib.sha256(b'{}').hexdigest(),
                'expected_trials':12,'trials_per_cell':1}))
            row={'run_id':'r','environment':'vcan','config':3,'attack_type':'spoofing','trial':0,
                'status':'VALID','blocked':True,'attack_success':False,'detected':False,
                'latency_s':None,'input_sha256':'abc'}
            trial_dir=root/'C3-spoofing-T000';trial_dir.mkdir()
            (trial_dir/'bus.jsonl').write_text('')
            row['artifact_sha256']={'bus.jsonl':hashlib.sha256(b'').hexdigest()}
            (trial_dir/'result.json').write_text(json.dumps(row))
            (root/'attempts.jsonl').write_text(json.dumps(row)+'\n')
            result=summarize(root)
            self.assertFalse(result['matrix_complete'])
            group=next(r for r in result['summary'] if r['config']==3 and r['attack_type']=='spoofing')
            self.assertEqual(group['undetected_trials'],1)
            self.assertIsNone(group['avg_detected_latency_s'])
            (trial_dir/'bus.jsonl').write_text('changed')
            with self.assertRaises(ValueError):summarize(root)
            (trial_dir/'bus.jsonl').write_text('')
            (root/'attempts.jsonl').write_text((json.dumps(row)+'\n')*2)
            with self.assertRaises(ValueError):summarize(root)
        self.assertEqual(trial_seed('replay',0),trial_seed('replay',0))


if __name__=='__main__':unittest.main()
