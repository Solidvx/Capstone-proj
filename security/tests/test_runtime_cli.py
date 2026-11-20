import json
from pathlib import Path
import socket
import struct
import hashlib
import tempfile
import unittest
from unittest.mock import patch, Mock

from security.ids.runtime import main, SocketCan, train_model


class RuntimeCliTests(unittest.TestCase):
    def test_replay_if_and_log_protection(self):
        # Real sklearn fit and CLI replay. No pickle/model deserialization.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            normal=root/'normal.jsonl'
            normal.write_text(''.join(json.dumps({'t':i*.1+offset,'can_id':cid,
                'data':'96be1068ffec4100'})+'\n' for i in range(40) for cid,offset in ((0x100,0),(0x102,.002))))
            manifest=root/'normal.manifest.json'
            manifest.write_text(json.dumps({'schema':'ids-normal-v2','status':'COMPLETE',
                'rejected_frames':0,'duration_s':4,'allowed_ids':[0x100,0x102],
                'accepted_frames':80,'capture_sha256':hashlib.sha256(normal.read_bytes()).hexdigest()}))
            model=train_model(normal,manifest_path=manifest)
            self.assertIsNotNone(model.model)
            replay=root/'attack.jsonl'
            replay.write_text(json.dumps({'t':0.0,'can_id':0x555,'data':'00'*8})+'\n'+
                              json.dumps({'t':0.9,'can_id':0x555,'data':'00'*8})+'\n'+
                              json.dumps({'tick':1.0})+'\n')
            log=root/'events.jsonl'
            args=['--replay',str(replay),'--train-normal',str(normal),'--normal-manifest',str(manifest),'--log',str(log)]
            self.assertEqual(main(args),0)
            records=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(records[0]['mode'],'rules+if')
            self.assertIn('UNKNOWN_ID',[r.get('reason') for r in records])
            findings=[r['finding'] for r in records if r.get('finding')]
            self.assertEqual(records[0]['finding_schema'],'ids-finding-v1')
            self.assertTrue(findings)
            self.assertEqual({r['source_id'] for r in findings},{records[0]['finding_source_id']})
            self.assertEqual(len({r['sequence'] for r in findings}),len(findings))
            evaluated=[r for r in records if r.get('result')=='MODEL_EVALUATION']
            self.assertEqual(len(evaluated),1)
            self.assertEqual(evaluated[0]['finding']['observed']['features']['msg_rate'],1.0)
            self.assertEqual(evaluated[0]['finding']['observed']['anomaly'],evaluated[0]['anomaly_score'])
            before=log.read_bytes()
            self.assertEqual(main(args),2)
            self.assertEqual(log.read_bytes(),before)
            measured=root/'measured.jsonl'
            measured_args=args[:];measured_args[measured_args.index(str(log))]=str(measured)
            self.assertEqual(main(measured_args+['--measure-resources']),0)
            measured_rows=[json.loads(line) for line in measured.read_text().splitlines()]
            summary=measured_rows[-1]
            self.assertEqual(summary['result'],'RESOURCE_SUMMARY')
            self.assertEqual(summary['status'],'COMPLETE')
            self.assertEqual(summary['counts']['completed_frames'],2)
            self.assertEqual(summary['counts']['completed_ticks'],1)
            self.assertEqual(summary['counts']['model_evaluations'],1)
            self.assertEqual(summary['durations']['feature_extraction']['calls'],1)
            self.assertEqual(summary['durations']['model_anomaly']['calls'],1)
            self.assertEqual(summary['model_artifact']['storage'],'trained_in_memory')
            self.assertIsNone(summary['model_artifact']['file_bytes'])
            self.assertEqual(len(summary['model_artifact']['state_sha256']),64)
            def core(rows):
                return [(r.get('timestamp'),r.get('can_id'),r.get('reason'),r.get('attack_type'),r.get('anomaly_score'),r['result'])
                        for r in rows if r.get('result') not in ('START','END','RESOURCE_SUMMARY')]
            self.assertEqual(core(records),core(measured_rows))

    def test_socketcan_codec_timeout_and_cleanup(self):
        fake=Mock()
        fake.recvmsg.return_value=(struct.pack('=IB3x8s',0x100,8,bytes(8)),
            [(socket.SOL_SOCKET,64,struct.pack('=qq',1000,0))],0,None)
        fake.send.return_value=16
        with patch('security.ids.runtime.socket.socket',return_value=fake), \
             patch('security.ids.runtime.socket.AF_CAN',29,create=True), \
             patch('security.ids.runtime.socket.CAN_RAW',1,create=True):
            transport=SocketCan('test-only')
            frame=transport.receive()
            self.assertEqual(frame.can_id,0x100)
            self.assertEqual(frame.dlc,8)
            payload=bytes.fromhex('0296010000000001')
            transport.send(payload)
            self.assertEqual(fake.send.call_args.args,(struct.pack('=IB3x8s',0x200,8,payload), socket.MSG_DONTWAIT))
            fake.recvmsg.side_effect=socket.timeout()
            self.assertIsNone(transport.receive())
            fake.send.return_value=1
            with self.assertRaises(OSError):transport.send(payload)
            transport.close()
            fake.close.assert_called_once()

    def test_invalid_capture_and_missing_key_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);capture=root/'input.jsonl';capture.write_text('{bad json}\n')
            args=['--replay',str(capture),'--rules-only','--log',str(root/'log.jsonl')]
            self.assertEqual(main(args),2)
            self.assertEqual(main(args+['--secoc-key',str(root/'missing')]),2)


if __name__=='__main__':unittest.main()
