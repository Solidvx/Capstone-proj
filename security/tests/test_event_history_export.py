import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('event_export',ROOT/'ivi_platform/scripts/export_event_history.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def store(tmp_path):
    folder=tmp_path/'store';folder.mkdir(mode=0o700)
    body=json.dumps({'schema':1,'event_id':'dummy-event','display':'배터리 이벤트'},ensure_ascii=False,separators=(',',':'))
    row={'schema':1,'sequence':'1','payload':body,'sha256':hashlib.sha256(('1\n'+body).encode()).hexdigest()}
    path=folder/'events-00000000000000000001.jsonl';path.write_text(json.dumps(row)+'\n');path.chmod(0o600)
    return folder,path,row


def test_export_preserves_source_and_creates_checksummed_new_output(tmp_path):
    directory,path,_=store(tmp_path);before=path.read_bytes()
    out=tmp_path/'export';manifest=module.export(directory,out)
    assert manifest['records']==1 and manifest['status']=='COMPLETE'
    assert hashlib.sha256((out/'events.jsonl').read_bytes()).hexdigest()==manifest['sha256']
    assert path.read_bytes()==before
    with pytest.raises(FileExistsError):module.export(directory,out)


def test_partial_tail_is_explicit_and_corruption_does_not_create_manifest(tmp_path):
    directory,path,row=store(tmp_path)
    with path.open('ab') as file:file.write(b'{partial')
    result=module.export(directory,tmp_path/'partial-export')
    assert result['status']=='COMPLETE_WITH_PARTIAL_TAILS' and result['partial_tail_files']==[path.name]
    row['sha256']='0'*64;path.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='checksum'):module.export(directory,tmp_path/'bad-export')
    assert not (tmp_path/'bad-export/manifest.json').exists()


def test_export_preserves_typed_incidents_without_inventing_rejections(tmp_path):
    directory,path,row=store(tmp_path)
    event=json.loads(row['payload'])
    links=[{'attack_type':'replay','incident_id':'01'*16,'rejection_id':'02'*16},
           {'attack_type':'flooding','incident_id':'03'*16}]
    event['typed_incidents']=links
    event['ecu_process']={'instance_id':'04'*16,'session_id':'05'*16,'risk_restored':True}
    event['ecu_restart_plan']={'operation_id':'06'*16,'instance_id':'07'*16}
    row['payload']=json.dumps(event)
    row['sha256']=hashlib.sha256(('1\n'+row['payload']).encode()).hexdigest()
    path.write_text(json.dumps(row)+'\n')
    before=path.read_bytes()
    module.export(directory,tmp_path/'typed-export')
    exported=json.loads((tmp_path/'typed-export/events.jsonl').read_text())
    assert exported['event']['typed_incidents']==links
    assert exported['event']['ecu_process']==event['ecu_process']
    assert exported['event']['ecu_restart_plan']==event['ecu_restart_plan']
    assert path.read_bytes()==before


def test_export_still_rejects_unrecognized_fields(tmp_path):
    directory,path,row=store(tmp_path)
    event=json.loads(row['payload']);event['unexpected_private_field']='dummy'
    row['payload']=json.dumps(event)
    row['sha256']=hashlib.sha256(('1\n'+row['payload']).encode()).hexdigest()
    path.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='unrecognized fields'):
        module.export(directory,tmp_path/'unknown-export')
    assert not (tmp_path/'unknown-export/manifest.json').exists()


def protection_store(tmp_path):
    from security.tests.test_protection_diagnostic import bodies
    directory,path,row=store(tmp_path)
    raw=bodies()[2][1]
    event=json.loads(row['payload'])
    event.update(category='protection-status',ecu_protection={
        'body_hex':raw.hex(),'instance_id':raw[:16].hex(),'lineage_id':raw[16:32].hex(),
        'incident_id':raw[32:48].hex(),'state':raw[48],'reason':raw[49],'phase':raw[50],
        'revision':'1','checkpoint_resumed':False,'state_confirmed':True,
        'session_id':'aa'*16,'sequence':'5','received_monotonic_ms':'123'},
        protection_link={'status':'unlinked','high_water_revision':'1','gap_possible':True})
    return directory,path,row,event


def write_event(path,row,event):
    row=dict(row,payload=json.dumps(event))
    row['sha256']=hashlib.sha256(('1\n'+row['payload']).encode()).hexdigest()
    path.write_text(json.dumps(row)+'\n')


def test_protection_export_preserves_reviewed_identity_and_gap_without_source_mutation(tmp_path):
    directory,path,row,event=protection_store(tmp_path);write_event(path,row,event);before=path.read_bytes()
    result=module.export(directory,tmp_path/'protection-export')
    exported=json.loads((tmp_path/'protection-export/events.jsonl').read_text())['event']
    assert exported['ecu_protection']==event['ecu_protection']
    assert exported['protection_link']==event['protection_link']
    assert path.read_bytes()==before and result['records']==1
    assert result['contains_gap_annotations'] is True


def test_clean_protection_link_is_not_reported_as_a_recording_gap(tmp_path):
    directory,path,row,event=protection_store(tmp_path)
    event['protection_link']['gap_possible']=False
    write_event(path,row,event)
    result=module.export(directory,tmp_path/'clean-protection-export')
    assert result['contains_gap_annotations'] is False


@pytest.mark.parametrize('field',['ecu_protection','protection_link'])
def test_new_protection_objects_reject_unknown_nested_fields(tmp_path,field):
    directory,path,row,event=protection_store(tmp_path)
    event[field]['unexpected_private_field']='public-dummy'
    write_event(path,row,event)
    with pytest.raises(ValueError,match='unrecognized protection'):
        module.export(directory,tmp_path/'bad-protection-export')
    assert not (tmp_path/'bad-protection-export/manifest.json').exists()


@pytest.mark.parametrize('mutation',['unconfirmed','negative-counter','lower-high-water','bad-record-id'])
def test_protection_export_rejects_unreviewed_or_ambiguous_link_shape(tmp_path,mutation):
    directory,path,row,event=protection_store(tmp_path)
    if mutation=='unconfirmed':event['ecu_protection']['state_confirmed']=False
    elif mutation=='negative-counter':event['ecu_protection']['revision']='-1'
    elif mutation=='lower-high-water':event['protection_link']['high_water_revision']='0'
    else:event['protection_link']['previous_event_id']='not-a-record-uuid'
    write_event(path,row,event)
    with pytest.raises(ValueError):module.export(directory,tmp_path/'bad-protection-export')
