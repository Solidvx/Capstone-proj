import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security.attack_simulator import ATTACKS
from security.experiments.analyze_roc import analyze, roc, SCOPE
from security.experiments.score_ids_captures import score_dataset, read_frames
from security.experiments.validate_m5_settings import validate
from security.experiments.inspect_evidence import inspect
from security.experiments.inspect_evidence import main as evidence_main
from security.ids.if_detector import sklearn_available


def manifest():
    return {'schema':'ids-window-evaluation-v1','scope':SCOPE,'environment':'synthetic',
        'model_id':'a'*64,'training_run_ids':['train'],'training_capture_sha256s':['b'*64]}


def scores():
    result=[]
    for index,purpose in enumerate(('calibration','evaluation')):
        for group,kind in enumerate(('',*ATTACKS)):
            for window in range(2):
                result.append({'run_id':f'{purpose}-{kind or "normal"}','purpose':purpose,
                    'source_sha256':hashlib.sha256(f'{index}-{group}'.encode()).hexdigest(),
                    'window_id':window,'label':int(bool(kind)),'attack_type':kind,
                    'complete':True,'score':2.0 if kind else 0.0})
    return result


class ExperimentPreparationTests(unittest.TestCase):
    def test_roc_perfect_ties_and_frozen_evaluation_threshold(self):
        rows=scores();result=analyze(rows,manifest())
        self.assertEqual(result['calibration_auc'],1)
        self.assertEqual(result['threshold_candidate'],0)
        self.assertFalse(result['normal_100_window_minimum_met'])
        self.assertFalse(result['official_trial_acceptance'])
        for row in rows:
            if row['purpose']=='evaluation' and row['label']==0:row['score']=3
        changed=analyze(rows,manifest())
        self.assertEqual(changed['threshold_candidate'],0)
        self.assertEqual(changed['evaluation']['fpr'],1)
        for row in rows:row['score']=1
        points,area=roc(rows)
        self.assertEqual(area,.5)
        self.assertEqual(points[0]['tpr'],0)
        self.assertIsNone(analyze(rows,manifest())['threshold_candidate'])

    def test_each_attack_must_meet_calibration_target_not_pooled_tpr(self):
        rows=scores()
        for row in rows:
            if row['purpose']=='calibration' and row['attack_type']=='replay':row['score']=0
        self.assertEqual(analyze(rows,manifest())['status'],'NO_FEASIBLE_THRESHOLD')

    def test_leakage_duplicates_bad_types_and_incomplete_windows_rejected(self):
        variants=[]
        for field,value in (('run_id','train'),('source_sha256','b'*64),('score',float('nan')),
                            ('score',True),('complete',False),('label',True),('window_id',5)):
            rows=scores();rows[0][field]=value;variants.append(rows)
        variants.append(scores()+[copy.deepcopy(scores()[0])])
        rows=scores();rows[-1]['source_sha256']=rows[0]['source_sha256'];variants.append(rows)
        for rows in variants:
            with self.assertRaises(ValueError):analyze(rows,manifest())
        with self.assertRaises(ValueError):analyze(scores(),None)

    def fixture_dataset(self,root):
        train=[]
        for i in range(40):
            for cid,offset in ((0x100,0),(0x102,.002)):
                train.append({'t':i*.1+offset,'can_id':cid,'data':'96be1068ffec4100'})
        path=root/'train.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in train))
        metadata={'schema':'ids-normal-v2','status':'COMPLETE','run_id':'train','environment':'synthetic',
            'duration_s':4,'allowed_ids':[256,258],'rejected_frames':0,'accepted_frames':80,
            'capture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        (root/'train.manifest.json').write_text(json.dumps(metadata))
        dataset={'schema':'ids-capture-evaluation-v1','environment':'synthetic',
            'training':{'capture':'train.jsonl','manifest':'train.manifest.json'},'captures':[]}
        for split in ('calibration','evaluation'):
            for group,kind in enumerate(('',*ATTACKS)):
                run=f'{split}-{kind or "normal"}';file=root/(run+'.jsonl')
                rate=20 if not kind else 100
                rows=[{'t':i/rate+.001+(group+1)*.00001+(split=='evaluation')*.000001,
                    'can_id':0x100,'data':'96be1068ffec4100'} for i in range(rate*3)]
                file.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                dataset['captures'].append({'path':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                    'run_id':run,'duration_s':3.5,'purpose':split,'label':int(bool(kind)),
                    'attack_type':kind,'status':'COMPLETE','environment':'synthetic'})
        path=root/'dataset.json';path.write_text(json.dumps(dataset));return path

    def test_capture_scoring_real_feature_extraction_and_new_outputs(self):
        class Model:
            model=type('Params',(),{'get_params':lambda self:{'random_state':42}})()
            def anomaly(self,vector):return vector[0]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dataset=self.fixture_dataset(root)
            with patch('security.experiments.score_ids_captures.train_model',return_value=Model()), \
                 patch('security.experiments.score_ids_captures.importlib.metadata.version',return_value='test'):
                result=score_dataset(dataset,root/'output')
                self.assertEqual(result['status'],'CANDIDATE_SELECTED')
                with self.assertRaises(FileExistsError):score_dataset(dataset,root/'output')
            rows=[json.loads(v) for v in (root/'output/window-scores.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),30) # 3 complete windows, not the partial .5s tail
            self.assertTrue(all(r['complete'] for r in rows))
            data=json.loads(dataset.read_text());data['captures'][0]['sha256']='f'*64
            dataset.write_text(json.dumps(data))
            with patch('security.experiments.score_ids_captures.train_model',return_value=Model()), \
                 patch('security.experiments.score_ids_captures.importlib.metadata.version',return_value='test'):
                with self.assertRaises(ValueError):score_dataset(dataset,root/'bad-output')
            self.assertFalse((root/'bad-output').exists())

    @unittest.skipUnless(sklearn_available(),'real sklearn unavailable')
    def test_actual_sklearn_score_pipeline_no_model_pickle(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=self.fixture_dataset(root)
            result=score_dataset(path,root/'real-if')
            self.assertIn(result['status'],('CANDIDATE_SELECTED','NO_FEASIBLE_THRESHOLD'))
            self.assertEqual(len(result['model_id']),64)
            self.assertFalse(result['official_trial_acceptance'])

    def test_frame_damage_and_unordered_times_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'frames.jsonl'
            for rows in ([],[{'t':0,'can_id':True,'data':'00'*8}],
                         [{'t':1,'can_id':256,'data':'00'*8},{'t':.5,'can_id':256,'data':'00'*8}]):
                path.write_text(''.join(json.dumps(v)+'\n' for v in rows))
                with self.assertRaises(ValueError):read_frames(path,2)

    def test_settings_reject_unresolved_remote_lifetime_and_clock_node_mismatch(self):
        path=Path(__file__).parents[1]/'experiments/m5-settings.template.json'
        template=json.loads(path.read_text())
        with self.assertRaises(ValueError):validate(template,'physical-can')
        fixed=json.loads(path.read_text().replace('REPLACE_','example_'))
        self.assertEqual(validate(fixed,'physical-can')['status'],'STATIC_VALID')
        changed=copy.deepcopy(fixed);changed['observer'][3]='other@example.test'
        with self.assertRaises(ValueError):validate(changed,'physical-can')
        changed=copy.deepcopy(fixed);changed['observer'][-1]=changed['observer'][-1].replace('{lifetime_s}','60')
        with self.assertRaises(ValueError):validate(changed,'physical-can')

    def seal(self,root):
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.name!='evidence-manifest.json'}
        (root/'evidence-manifest.json').write_text(json.dumps({'schema':'can-evidence-v1','run_id':'test',
            'environment':'vcan','interface':'vcan0','protocol':'ICD-v1.6','files':files}))

    def test_seal_rejects_environment_mismatch_before_creating_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('candump.log','receiver.jsonl'):(root/name).write_text('fixture')
            argv=['inspect_evidence','--input-dir',directory,'--mode','tamper','--seal',
                  '--run-id','test','--environment','vcan','--interface','can0']
            with patch('sys.argv',argv),patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:evidence_main()
            self.assertEqual(error.exception.code,2)
            self.assertFalse((root/'evidence-manifest.json').exists())

    def test_long_gap_failsafe_requires_receiver_acceptance_and_independent_counter(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw1='0001012741000000';raw2='0102020a41000000'
            auth1='aabbccdd00000000';auth2='abcd123400000001'
            lines=[f'(0.000000) vcan0 101#{raw1}',f'(0.002000) vcan0 103#{auth1}']
            for i in range(120):
                t=.1+i*.1
                lines.extend([f'({t:.6f}) vcan0 100#96be1068ffec4100',f'({t+.002:.6f}) vcan0 102#aabbccdd{i:08x}'])
            lines.extend([f'(13.000000) vcan0 101#{raw2}',f'(13.002000) vcan0 103#{auth2}'])
            (root/'candump.log').write_text('\n'.join(lines)+'\n')
            rows=[{'result':'FRAME','run_id':'test','can_id':0x103,'data':auth,'source_data':raw,
                   'process_result':2,'secoc_on':True} for auth,raw in ((auth1,raw1),(auth2,raw2))]
            (root/'receiver.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal(root)
            self.assertEqual(inspect(root,'failsafe')['status'],'CONFIRMED')
            rows[1]['process_result']=3
            (root/'receiver.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal(root)
            with self.assertRaises(ValueError):inspect(root,'failsafe')
            (root/'candump.log').write_text('changed')
            with self.assertRaises(ValueError):inspect(root,'failsafe')

    def test_mac_recovery_rejects_wrong_counter_and_false_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);lines=[];rows=[]
            for i,(soc,counter,result,last_good) in enumerate(((150,0,2,75),(200,1,3,75),(140,1,2,70))):
                raw=f'{soc:02x}be1068ffec4100';auth=f'aabbccdd{counter:08x}'
                lines.extend([f'({i:.6f}) vcan0 100#{raw}',f'({i+.002:.6f}) vcan0 102#{auth}'])
                rows.append({'result':'FRAME','run_id':'test','can_id':0x102,'data':auth,'source_data':raw,
                    'process_result':result,'secoc_on':True,'soc':last_good,'message':'reason=MAC_FAIL' if i==1 else 'verified'})
            (root/'candump.log').write_text('\n'.join(lines)+'\n')
            (root/'receiver.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal(root)
            self.assertEqual(inspect(root,'tamper')['status'],'CONFIRMED')
            rows[1]['soc']=100;rows[1]['process_result']=2
            (root/'receiver.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal(root)
            self.assertEqual(inspect(root,'tamper')['status'],'FAIL')


if __name__=='__main__':unittest.main()
