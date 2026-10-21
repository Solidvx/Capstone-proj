import csv
import tempfile
import unittest
from pathlib import Path
from analyze_ivi004 import analyze, FIELDS

BOOT = '12345678-1234-4234-8234-123456789abc'


def sample(sid=1, state='FRAME_SWAPPED'):
    prefix = ['PERF-PRE-001', BOOT, str(sid)]
    rows = [prefix+[stage, str(t), 'PENDING', '', '']
            for stage, t in zip(('T1','T2','T3'), (1000000,2000000,3000000))]
    if state == 'FRAME_SWAPPED':
        rows.append(prefix+['T4','4000000',state,'QT_SIGNAL_PROXY_ONLY',str(sid)])
    elif state == 'NOT_RENDERED':
        rows.append(prefix+['RESULT','',state,'COALESCED_BEFORE_SYNC','9'])
    elif state == 'INDETERMINATE':
        rows.append(prefix+['RESULT','',state,'NO_MATCHING_SWAP_BEFORE_EXIT',''])
    return rows


class Check(unittest.TestCase):
    def run_rows(self, rows, expected=1):
        with tempfile.TemporaryDirectory(dir='tmp') as td:
            p = Path(td)/'fixture.csv'
            with p.open('w', newline='') as f:
                w=csv.writer(f); w.writerow(FIELDS); w.writerows(rows)
            return analyze(p, expected)

    def test_normal(self):
        r=self.run_rows(sample())
        self.assertEqual(r['intervals']['T1-T4']['mean_ms'],3)
        self.assertEqual(r['formal_verdict'],'NOT_ASSESSED')

    def test_states_and_shortfall(self):
        r=self.run_rows(sample()+sample(2,'NOT_RENDERED')+sample(3,'INDETERMINATE')+sample(4,'PENDING'),300)
        self.assertEqual(r['counts'],{'FRAME_SWAPPED':1,'NOT_RENDERED':1,'INDETERMINATE':2})
        self.assertEqual(r['shortfall'],299)
        self.assertEqual(r['completion_fraction_of_recorded'],.25)

    def test_all_pending(self):
        r=self.run_rows(sample(state='PENDING')[:1])
        self.assertIsNone(r['intervals']['T1-T4']['mean_ms'])

    def test_duplicate_frame(self):
        rows=sample()+sample(2);rows[-1][-1]='1'
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_duplicate_and_terminal_conflict(self):
        for rows in (sample()+[sample()[0]],sample()+[sample(state='NOT_RENDERED')[-1]]):
            with self.assertRaises(ValueError):self.run_rows(rows)

    def test_reverse_time(self):
        rows=sample();rows[-1][4]='1'
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_mixed_identity(self):
        rows=sample()+sample(2);rows[-1][0]='OTHER'
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_placeholder(self):
        rows=sample();rows[0][1]='local'
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_bad_result(self):
        rows=sample(state='INDETERMINATE');rows[-1][6]='UNKNOWN'
        with self.assertRaises(ValueError):self.run_rows(rows)

    def test_missing_initial_stage(self):
        with self.assertRaises(ValueError):self.run_rows(sample()[1:])

    def test_latency_failure(self):
        rows=sample();rows[-1][4]='102000000'
        self.assertIn('LATENCY_TARGET_EXCEEDED',self.run_rows(rows)['review_flags'])

    def test_shared_time_flag(self):
        self.assertIn('SHARED_T4_TIMESTAMP_REVIEW',self.run_rows(sample()+sample(2))['review_flags'])


if __name__=='__main__': unittest.main()
