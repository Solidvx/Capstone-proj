import json
import tempfile
import unittest
from pathlib import Path
from compare_ivi_can import compare,read_can


class Check(unittest.TestCase):
    def test_preserved_physical_evidence(self):
        root=Path(__file__).resolve().parents[1]/'raw/received/23H10M'
        r=compare(root/'00H12M/11can.log',root/'receiver.jsonl','delta')
        self.assertTrue(r['exact_sequence_match'])
        self.assertEqual(r['can_frames'],450)
        self.assertEqual(r['authenticated_bms_log_count'],225)
        self.assertEqual(r['soc_decode_mismatches'],0)
        self.assertEqual(r['counter_discontinuities'],[])
        self.assertEqual(r['bms_period_ms']['outside_90_110'],0)

    def test_absolute_and_gap(self):
        with tempfile.TemporaryDirectory(dir='tmp') as td:
            can=Path(td)/'can.log'; rx=Path(td)/'rx.jsonl'
            rows=[(256,'a9c81068ffec4100'),(258,'0000000000000000'),(256,'a9c81068ffec4100'),(258,'0000000000000002')]
            can.write_text('\n'.join(f'({100+i//2*.1+(i%2)*.002:.6f}) can0 {cid:03X}#{data}' for i,(cid,data) in enumerate(rows)))
            rx.write_text('\n'.join(json.dumps({'result':'FRAME','run_id':'TEST','can_id':cid,'data':data,'timestamp_ns':i,'secoc_on':True}) for i,(cid,data) in enumerate(rows)))
            r=compare(can,rx,'absolute')
            self.assertTrue(r['exact_sequence_match'])
            self.assertEqual(r['bms_period_ms']['mean'],100)
            self.assertEqual(len(r['counter_discontinuities']),1)
            rx.write_text(rx.read_text().splitlines()[0]+'\n')
            r=compare(can,rx,'absolute')
            self.assertFalse(r['exact_sequence_match'])
            self.assertEqual(r['first_difference_index'],1)

    def test_bad_rows(self):
        for text in ['(100.0) can0 100##1AA','(100.0) can0 100#A','(100.0) can0 100#AA\n(99.0) can0 100#AA','CAN ERROR']:
            with tempfile.TemporaryDirectory(dir='tmp') as td:
                p=Path(td)/'can.log';p.write_text(text)
                with self.assertRaises(ValueError):read_can(p,'absolute')


if __name__=='__main__':unittest.main()
