import json

import pytest

from common.test_ecu_ivi_products import complete_observation_rows


def test_live_UTF8_tail_waits_for_a_complete_line_without_losing_committed_rows(tmp_path):
    path=tmp_path/'observation.jsonl'
    first=b'{"result":"READY"}\n'
    next_row=(json.dumps({'text':'연결 확인'},ensure_ascii=False)+'\n').encode('utf-8')
    partial=next_row.index('연'.encode('utf-8'))+1
    path.write_bytes(first+next_row[:partial])
    assert complete_observation_rows(path)==[{'result':'READY'}]
    path.write_bytes(first+next_row)
    assert complete_observation_rows(path)==[{'result':'READY'},{'text':'연결 확인'}]


@pytest.mark.parametrize('data',[b'bad-json\n',b'{"text":"\xff"}\n'])
def test_completed_corruption_is_never_ignored(tmp_path,data):
    path=tmp_path/'observation.jsonl';path.write_bytes(data)
    with pytest.raises((json.JSONDecodeError,UnicodeDecodeError)):
        complete_observation_rows(path)
