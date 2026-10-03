import argparse
import copy
import hashlib
import json
from pathlib import Path
import socket
import struct
import io
import tempfile
import unittest
from unittest.mock import Mock, patch

from security.can_socket import SocketCanTransport
from security.experiments.analyze_normal_fpr import analyze, POLICY
from security.experiments.bus_observer import collect
from security.experiments.run_normal_fpr import run
from security.experiments.run_ablation import Child


class NormalFprTests(unittest.TestCase):
    def fixture(self,root,count=100,alert_windows=(2,5)):
        run='test';start=1_000_000_000;frames=[]
        stats={'rx_errors':3,'rx_dropped':0,'tx_errors':0}
        for i in range(count*10):
            for cid,offset in ((0x100,0),(0x102,2_000_000)):
                frames.append({'result':'BUS_FRAME','run_id':run,'timestamp_ns':str(start+i*100_000_000+offset),
                    'can_id':cid,'dlc':8,'data':'96be1068ffec4100','extended':False,'remote':False,'error':False})
        for window in alert_windows:
            for offset in (20_000_000,40_000_000): # 2 alerts, but 1 FP window
                frames.append({'result':'BUS_FRAME','run_id':run,'timestamp_ns':str(start+window*1_000_000_000+offset),
                    'can_id':0x200,'dlc':8,'data':'0164010000000000','extended':False,'remote':False,'error':False})
        frames.sort(key=lambda row:int(row['timestamp_ns']))
        ready={'result':'READY','run_id':run,'interface':'vcan0','timestamp_ns':str(start),
            'rx_overflow_tracking':True,'stats_before':stats,'requested_duration_s':count}
        end={'result':'END','run_id':run,'interface':'vcan0','timestamp_ns':str(start+count*1_000_000_000),
            'stats_after':copy.deepcopy(stats),'status':'COMPLETE','rx_overflow':0,'frames':len(frames)}
        (root/'bus.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in [ready,*frames,end]))
        for name,fields in (('ids-console',{'mode':'rules+if','send_alerts':True}),
                            ('normal',{'secoc_on':True}),('receiver',{'secoc_on':True})):
            (root/(name+'.jsonl')).write_text(json.dumps({'result':'READY','run_id':run,**fields})+'\n')
        (root/'settings.json').write_text(json.dumps({r:['test','{run_id}'] for r in
            ('observer','receiver_on','receiver_off','normal_sender','ids')}))
        manifest={'schema':'normal-wire-fpr-v1','run_id':run,'environment':'vcan','interface':'vcan0',
            'normal_only':True,'status':'COMPLETE','managed_alive_until_capture_end':True,
            'warmup_ns':0,'windows':count,'window_policy':POLICY}
        (root/'manifest.json').write_text(json.dumps(manifest));self.rehash(root)

    def rehash(self,root):
        path=root/'manifest.json';manifest=json.loads(path.read_text())
        manifest['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()
            if p.is_file() and p.name!='manifest.json'}
        path.write_text(json.dumps(manifest))

    def test_wire_fpr_counts_windows_not_alerts_and_requires_100(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            result=analyze(root)
            self.assertEqual(result['fp_windows'],2);self.assertEqual(result['fpr'],.02)
            self.assertEqual(result['alerts_by_type']['1'],4);self.assertEqual(result['status'],'PASS')
            self.assertFalse(result['physical_evidence_target_met']);self.assertFalse(result['official_acceptance'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root,99)
            self.assertEqual(analyze(root)['status'],'INSUFFICIENT_WINDOWS')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root,100,tuple(range(6)))
            self.assertEqual(analyze(root)['status'],'FAIL')

    def test_interrupt_loss_missing_bounds_frames_and_bad_alert_rejected(self):
        for damage in ('interrupt','overflow','stats','short','unordered','missing','bad-alert','bad-run','type0'):
            with self.subTest(damage=damage),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);self.fixture(root)
                rows=[json.loads(v) for v in (root/'bus.jsonl').read_text().splitlines()]
                if damage=='interrupt':rows[-1]['status']='INTERRUPTED'
                elif damage=='overflow':rows[-1]['rx_overflow']=1
                elif damage=='stats':rows[-1]['stats_after']['rx_dropped']=1
                elif damage=='short':rows[-1]['timestamp_ns']=str(99_000_000_000)
                elif damage=='unordered':rows[2]['timestamp_ns']='0'
                elif damage=='missing':rows=[r for r in rows if not (r['result']=='BUS_FRAME' and r['can_id']==0x102)]
                elif damage=='bad-run':rows[2]['run_id']='other'
                else:
                    for r in rows:
                        if r.get('can_id')==0x200:r['data']=('ff' if damage=='bad-alert' else '00')+r['data'][2:]
                (root/'bus.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));self.rehash(root)
                if damage=='type0':self.assertEqual(analyze(root)['fp_windows'],0)
                else:
                    with self.assertRaises(ValueError):analyze(root)

    def test_stopped_or_non_transmitting_ids_and_hash_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            row=json.loads((root/'ids-console.jsonl').read_text());row['send_alerts']=False
            (root/'ids-console.jsonl').write_text(json.dumps(row));self.rehash(root)
            with self.assertRaises(ValueError):analyze(root)
            (root/'normal.jsonl').write_text('changed')
            with self.assertRaises(ValueError):analyze(root)

    def test_failed_process_launch_closes_both_logs(self):
        output=io.StringIO();errors=io.StringIO()
        with patch.object(Path,'open',side_effect=(output,errors)), \
                patch('security.experiments.run_ablation.subprocess.Popen',side_effect=OSError('launch failed')):
            with self.assertRaises(OSError):Child(['test'],Path('unused'),'child')
        self.assertTrue(output.closed);self.assertTrue(errors.closed)

    def test_socket_overflow_metadata_and_truncation(self):
        fake=Mock();raw=struct.pack('=IB3x8s',0x100,8,bytes(8))
        option=getattr(socket,'SO_RXQ_OVFL',40)
        fake.recvmsg.return_value=(raw,[(socket.SOL_SOCKET,option,struct.pack('=I',7))],0,None)
        with patch('security.can_socket.socket.socket',return_value=fake), \
                patch('security.can_socket.socket.AF_CAN',29,create=True), \
                patch('security.can_socket.socket.CAN_RAW',1,create=True):
            with SocketCanTransport('test-only',track_rx_overflow=True) as bus:
                self.assertEqual(bus.receive().can_id,0x100);self.assertEqual(bus.rx_overflow,7)
                fake.recvmsg.return_value=(raw,[],socket.MSG_CTRUNC,None)
                with self.assertRaises(OSError):bus.receive()

    def test_observer_interrupt_preserves_end_not_complete(self):
        bus=Mock();bus.rx_overflow=0;bus.receive.side_effect=KeyboardInterrupt();rows=[]
        with patch('security.experiments.bus_observer.interface_stats',return_value={}), \
                patch('security.experiments.bus_observer.time.monotonic_ns',side_effect=(0,0,5)):
            self.assertEqual(collect(bus,'test','vcan0',1,rows.append),130)
        self.assertEqual(rows[-1]['status'],'INTERRUPTED');self.assertEqual(rows[-1]['frames'],0)

    def test_managed_child_failure_preserves_invalid_artifacts_and_cleanup(self):
        class ChildFake:
            all=[]
            def __init__(self,command,root,name):
                self.name=name;self.stopped=False;self.process=Mock();self.process.poll.return_value=None
                self.all.append(self);(root/(name+'.jsonl')).write_text('{}\n')
            def ready(self,run):
                if self.name=='ids-console':raise RuntimeError('failed before READY')
            def snapshot(self):return [{'result':'READY','secoc_on':True}]
            def stop(self):self.stopped=True
        with tempfile.TemporaryDirectory() as directory,patch('security.experiments.run_normal_fpr.Child',ChildFake):
            args=argparse.Namespace(output_dir=str(Path(directory)/'run'),warmup=1,windows=3,
                run_id='test',environment='vcan',interface='vcan0')
            result=run({r:['test','{run_id}'] for r in ('receiver_on','normal_sender','ids')},args)
            self.assertEqual(result['status'],'INVALID');self.assertTrue(all(c.stopped for c in ChildFake.all))
            manifest=json.loads((Path(args.output_dir)/'manifest.json').read_text())
            self.assertFalse(manifest['managed_alive_until_capture_end'])
            self.assertIn('ids-console.jsonl',manifest['files'])


if __name__=='__main__':unittest.main()
