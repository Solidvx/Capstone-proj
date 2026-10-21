import json
from pathlib import Path
import socket
import struct
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
            normal.write_text(''.join(json.dumps({'t':i*.1,'can_id':0x100,
                'data':'96be1068ffec4100'})+'\n' for i in range(41)))
            model=train_model(normal)
            self.assertIsNotNone(model.model)
            replay=root/'attack.jsonl'
            replay.write_text(json.dumps({'t':0.0,'can_id':0x555,'data':'00'*8})+'\n'+
                              json.dumps({'tick':1.0})+'\n')
            log=root/'events.jsonl'
            args=['--replay',str(replay),'--train-normal',str(normal),'--log',str(log)]
            self.assertEqual(main(args),0)
            records=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(records[0]['mode'],'rules+if')
            self.assertIn('UNKNOWN_ID',[r.get('reason') for r in records])
            before=log.read_bytes()
            self.assertEqual(main(args),2)
            self.assertEqual(log.read_bytes(),before)

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
