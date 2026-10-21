import json
import os
from pathlib import Path
import random
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

from security.attack_simulator import build_attack_frame
from security.attacks.attack_simulator import build_frame
from security.experiments.run_ablation import summarize_observations, Child
from security.experiments import run_ablation
from security.experiments.remote_process import supervise
from security.ids.runtime_detector import RuntimeDetector, Observation
from security.tests.test_runtime_ids import auth, BMS, KEY


class ThreeNodeTests(unittest.TestCase):
    def test_remote_start_failure_restores_signal_handlers(self):
        signals=(signal.SIGHUP,signal.SIGINT,signal.SIGTERM)
        before={sig:signal.getsignal(sig) for sig in signals}
        with self.assertRaises(FileNotFoundError):
            supervise(['/nonexistent-chg022-test-executable'],1)
        self.assertEqual(before,{sig:signal.getsignal(sig) for sig in signals})

    def settings(self):
        path=Path(__file__).parents[1]/'experiments/m5-settings.template.json'
        return json.loads(path.read_text().replace('REPLACE_', 'test_'))

    def test_matrix_schedules_exactly_1200_unique_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            settings=root/'settings.json'
            settings.write_text(json.dumps(self.settings()))
            calls=[]
            def trial(settings,args,config,attack,index,path):
                calls.append((config,attack,index))
                return {'status':'VALID'}
            with patch.object(run_ablation,'run_trial',side_effect=trial), patch.object(run_ablation.time,'sleep'):
                status=run_ablation.main(['--settings',str(settings),'--output-dir',str(root/'run'),
                    '--run-id','matrix-test','--environment','physical-can','--interface','can0',
                    '--trials','100','--confirm-isolated-test-bus','--confirm-product-ecu-stopped'])
            self.assertEqual(status,0)
            self.assertEqual(len(calls),1200)
            self.assertEqual(len(set(calls)),1200)
            self.assertEqual(len((root/'run/attempts.jsonl').read_text().splitlines()),1200)

    def test_wrong_first_type_does_not_count_as_expected_type(self):
        tx=[{'result':'TX_ACCEPTED','can_id':0,'data':'00'*8}]
        bus=[{'result':'BUS_FRAME','can_id':0,'data':'00'*8,'timestamp_ns':'1000000000'}]
        bus.append({'result':'BUS_FRAME','can_id':0x200,'data':'0164000000000000','timestamp_ns':'1100000000'})
        result=summarize_observations(3,'flooding',tx,bus,[],[])
        self.assertTrue(result['detected'])
        self.assertFalse(result['expected_type_detected'])
        bus.append({'result':'BUS_FRAME','can_id':0x200,'data':'0464000000000000','timestamp_ns':'1200000000'})
        result=summarize_observations(3,'flooding',tx,bus,[],[])
        self.assertEqual(result['observed_attack_codes'],[1,4])
        self.assertEqual(result['first_alert_attack_code'],1)
        self.assertTrue(result['expected_type_detected'])
        self.assertAlmostEqual(result['expected_type_latency_s'],.2)
        self.assertFalse(result['ivi_expected_type_published'])
        receiver=[{**bus[-1],'result':'FRAME','process_result':2}]
        self.assertTrue(summarize_observations(3,'flooding',tx,bus,receiver,[])['ivi_expected_type_published'])
        self.assertIsNone(summarize_observations(2,'flooding',tx,bus,[],[])['expected_type_detected'])

    def test_real_attack_payloads_reach_expected_wire_codes(self):
        cases=[(attack,code,factory) for attack,code in
               [('fuzzy',1),('replay',2),('spoofing',3),('flooding',4)]
               for factory in (build_attack_frame,lambda a,r:build_frame(a,r,0))]
        for attack,code,factory in cases:
            with self.subTest(attack=attack,factory=factory):
                detector=RuntimeDetector(key=KEY)
                detector.observe(Observation(0,0x100,BMS))
                detector.observe(Observation(.002,0x102,auth(0)))
                events=[]
                rng=random.Random(42)
                if attack=='replay':
                    detector.observe(Observation(.1,0x100,BMS))
                    events=detector.observe(Observation(.102,0x102,auth(0)))
                else:
                    for i in range(110 if attack=='flooding' else 1):
                        cid,data=factory(attack,rng)
                        events+=detector.observe(Observation(.1+i*.001,cid,data))
                matching=[e for e in events if e.attack_type==code]
                self.assertTrue(matching)
                payload=matching[0].alert_payload(1)
                self.assertEqual(len(payload),8)
                self.assertEqual(payload[0],code)

    def test_remote_child_exits_after_control_pipe_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            pidfile=root/'pid'
            command=[sys.executable,'-m','security.experiments.remote_process','--duration','10','--',
                     sys.executable,'-c',
                     'import os,time,pathlib; pathlib.Path('+repr(str(pidfile))+').write_text(str(os.getpid())); '
                     'print(\'{"result":"READY","run_id":"test"}\',flush=True); time.sleep(30)']
            child=Child(command,root,'remote')
            try:
                child.ready('test',timeout=5)
                pid=int(pidfile.read_text())
            finally:
                child.stop()
            self.assertIsNotNone(child.process.returncode)
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)


if __name__=='__main__':unittest.main()
