import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from security.experiments.analyze_roc import analyze, metrics
from security.experiments.render_roc import render
from security.experiments.verify_reproducibility import compare
from security.experiments.summarize_ablation import main as summary_main
from security.tests.test_experiment_preparation import scores, manifest
from security.attack_simulator import ATTACKS


class AnalysisArtifactTests(unittest.TestCase):
    def test_confusion_metrics_and_zero_denominator(self):
        result=metrics(scores(),0)
        for key in ('precision','recall','f1','balanced_accuracy','mcc','tnr'):self.assertEqual(result[key],1)
        negative=metrics(scores(),3)
        self.assertIsNone(negative['precision']);self.assertIsNone(negative['mcc'])
        self.assertEqual(negative['fnr'],1)

    def test_roc_svg_is_valid_xml_and_rejects_bad_auc_or_coordinates(self):
        result=analyze(scores(),manifest());svg=render(result)
        root=ET.fromstring(svg)
        self.assertEqual(root.tag,'{http://www.w3.org/2000/svg}svg')
        self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}polyline')),2)
        self.assertIn('not live 0x200',svg)
        for field,value in (('evaluation_auc',.5),('evaluation_roc',[{'fpr':-1,'tpr':0},{'fpr':1,'tpr':1}])):
            bad=copy.deepcopy(result);bad[field]=value
            with self.assertRaises(ValueError):render(bad)
        result['status']='<script>alert(1)</script>'
        self.assertNotIn('<script>',render(result))

    def matrices(self,root):
        paths=[root/'previous',root/'current']
        contract={'environment':'vcan','trials_per_cell':100,'fixture':'fixture',
            'configuration_variable':'receiver','settings_sha256':'a'*64,'tool_sha256':{'runner':'b'*64},'phases':{'duration':3}}
        for i,path in enumerate(paths):
            path.mkdir();(path/'manifest.json').write_text(json.dumps({**contract,'run_id':f'run-{i}'}))
            (path/'attempts.jsonl').write_text(json.dumps({'config':1,'attack_type':'fuzzy','trial':0,'seed':42,'input_sha256':'c'*64})+'\n')
        rows=[{'config':c,'attack_type':a,'attack_success_rate':0.0,'valid_trials':100} for c in (1,2,3) for a in ATTACKS]
        return paths,[{'matrix_complete':True,'summary':copy.deepcopy(rows)} for _ in paths]

    def test_repro_percentage_point_boundary_zero_baseline_and_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,results=self.matrices(Path(directory))
            results[1]['summary'][0]['attack_success_rate']=.05
            with patch('security.experiments.verify_reproducibility.summarize',side_effect=copy.deepcopy(results)):
                self.assertEqual(compare(*paths)['status'],'PASS')
            results[1]['summary'][0]['attack_success_rate']=.05001
            with patch('security.experiments.verify_reproducibility.summarize',side_effect=copy.deepcopy(results)):
                self.assertEqual(compare(*paths)['status'],'FAIL')
            path=paths[1]/'manifest.json';record=json.loads(path.read_text());record['phases']['duration']=4
            path.write_text(json.dumps(record))
            with patch('security.experiments.verify_reproducibility.summarize',side_effect=copy.deepcopy(results)):
                with self.assertRaises(ValueError):compare(*paths)

    def test_repro_same_run_or_changed_inputs_or_incomplete_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths,results=self.matrices(Path(directory))
            with self.assertRaises(ValueError):compare(paths[0],paths[0])
            path=paths[1]/'attempts.jsonl';row=json.loads(path.read_text());row['seed']=43;path.write_text(json.dumps(row))
            with patch('security.experiments.verify_reproducibility.summarize',side_effect=copy.deepcopy(results)):
                with self.assertRaises(ValueError):compare(*paths)
            results[1]['matrix_complete']=False
            with patch('security.experiments.verify_reproducibility.summarize',side_effect=results):
                with self.assertRaises(ValueError):compare(*paths)

    def test_summary_csv_preserves_ratio_and_undefined_blanks(self):
        result={'matrix_complete':True,'environment':'vcan','summary':[
            {'config':1,'attack_type':'fuzzy','detected_rate':0.0,'avg_detected_latency_s':None}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'summary.json';csvfile=root/'summary.csv'
            with patch('security.experiments.summarize_ablation.summarize',return_value=result),patch('builtins.print'):
                self.assertEqual(summary_main(['--input-dir','unused','--output',str(output),'--csv-output',str(csvfile)]),0)
                self.assertEqual(summary_main(['--input-dir','unused','--output',str(root/'new.json'),'--csv-output',str(csvfile)]),2)
            with csvfile.open() as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(rows[0]['environment'],'vcan');self.assertEqual(rows[0]['detected_rate'],'0.0')
            self.assertEqual(rows[0]['avg_detected_latency_s'],'')
            self.assertFalse((root/'new.json').exists())


if __name__=='__main__':unittest.main()
