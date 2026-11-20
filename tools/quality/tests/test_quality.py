from pathlib import Path
import pytest
from tools.quality.coverage import aggregate
from tools.quality.static_analysis import evaluate
from tools.quality.ctest_gate import EXPECTED, validate_names, validate_junit
import xml.etree.ElementTree as ET


def test_coverage_merges_duplicates_but_keeps_unexecuted_lines():
    root = Path('/example')
    doc = {'format_version': '2', 'files': [
        {'file': '/example/main.cpp', 'lines': [{'line_number': 1, 'count': 0}]},
        {'file': '/example/src/app/failsafe_sm.cpp', 'lines': [
            {'line_number': 1, 'count': 1, 'branches': [{'count': 1}, {'count': 0}]}]}]}
    result = aggregate([doc, doc], root, 'ecu', {'main.cpp', 'src/app/failsafe_sm.cpp'})
    assert result['lines'] == {'covered': 1, 'total': 2, 'percent': 50.0}
    assert result['failsafe_branches']['percent'] == 50
    assert result['status'] == 'FAIL'
    with pytest.raises(ValueError, match='incomplete'):
        aggregate([doc], root, 'ecu', {'main.cpp', 'missing.cpp'})


def test_empty_and_missing_branch_coverage_fail_closed():
    with pytest.raises(ValueError):
        aggregate([], Path('/example'), 'ecu', {'main.cpp'})
    doc = {'format_version': '2', 'files': [{'file': '/example/main.cpp',
        'lines': [{'line_number': 1, 'count': 1}]}]}
    with pytest.raises(ValueError, match='branch'):
        aggregate([doc], Path('/example'), 'ecu', {'main.cpp'})


def test_uncovered_branches_preserve_exception_identity_and_do_not_change_gate():
    root=Path('/example');name='src/app/failsafe_sm.cpp'
    def document(count):
        return {'format_version':'2','files':[{'file':str(root/name),'lines':[{
            'line_number':51,'count':1,'function_name':'clocked_evaluate',
            'branches':[{'count':3,'throw':False,'source_block_id':4,'destination_block_id':5},
                        {'count':count,'throw':True,'source_block_id':4,'destination_block_id':9}]}]}]}
    result=aggregate([document(0),document(0)],root,'ecu',{name})
    assert result['lines']['percent']==100 and result['failsafe_branches']['percent']==50
    assert result['status']=='FAIL'
    assert result['uncovered_failsafe_branches']==[{'file':name,'line':51,'function':'clocked_evaluate',
        'index':1,'throw':True,'source_block_id':4,'destination_block_id':9}]
    result=aggregate([document(0),document(1)],root,'ecu',{name})
    assert result['status']=='PASS' and result['uncovered_failsafe_branches']==[]
    assert result['failsafe_branches']['total']==2


def test_static_errors_block_warnings_do_not_and_tool_failure_is_invalid():
    def report(severity):
        return f'<results><cppcheck version="test"/><errors><error severity="{severity}" id="injected"/></errors></results>'
    assert evaluate(report('warning'), 2, 1)['status'] == 'PASS'
    assert evaluate(report('error'), 2, 1)['status'] == 'FAIL'
    for code, count in ((1, 1), (0, 0)):
        with pytest.raises(ValueError):
            evaluate(report('warning'), code, count)
    with pytest.raises(ValueError):
        evaluate('<results/>', 0, 1)


def test_ctest_gate_requires_inventory_and_explicit_skip():
    names = ['test_' + name for name in EXPECTED['ivi']]
    validate_names(names, 'ivi')
    for bad in ([], names[:-1], names + [names[0]]):
        with pytest.raises(ValueError):
            validate_names(bad, 'ivi')
    root = ET.Element('testsuite')
    for name in names:
        case = ET.SubElement(root, 'testcase', name=name)
        if name == 'test_socketcan_receiver':
            ET.SubElement(case, 'skipped')
    with pytest.raises(ValueError, match='skip'):
        validate_junit(root, 'ivi', False)
    assert validate_junit(root, 'ivi', True)['executed'] == len(names)-1
    ET.SubElement(root[0], 'failure')
    with pytest.raises(ValueError, match='failed'):
        validate_junit(root, 'ivi', True)


def test_ecu_vcan_skips_are_explicit_but_unit_skips_still_fail():
    root=ET.Element('testsuite')
    for name in sorted(EXPECTED['ecu']):
        case=ET.SubElement(root,'testcase',name='test_'+name)
        if name=='can_receive_lifecycle':ET.SubElement(case,'skipped')
    with pytest.raises(ValueError,match='skip'):validate_junit(root,'ecu',False)
    assert validate_junit(root,'ecu',True)['skipped']==['test_can_receive_lifecycle']
    case=next(c for c in root if c.get('name')=='test_publisher')
    ET.SubElement(case,'skipped')
    with pytest.raises(ValueError,match='skip'):validate_junit(root,'ecu',True)


def test_integrated_inventory_requires_every_product_and_rejects_skips():
    names=sorted('test_'+name for name in EXPECTED['ivi-integrated'])
    assert len(names)==44
    validate_names(names,'ivi-integrated')
    for missing in ('test_can_receive_recovery_product','test_can_receive_recovery_success_product','test_bms_recovery_success_product','test_protection_event_product'):
        with pytest.raises(ValueError,match='inventory'):
            validate_names([n for n in names if n!=missing],'ivi-integrated')
    root=ET.Element('testsuite')
    for name in names:ET.SubElement(root,'testcase',name=name)
    assert validate_junit(root,'ivi-integrated',False)['executed']==44
    ET.SubElement(root[0],'skipped')
    for allow in (False,True):
        with pytest.raises(ValueError,match='skip'):
            validate_junit(root,'ivi-integrated',allow)
