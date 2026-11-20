import hashlib
import json

import pytest

from security.experiments.plot_results import ekf_data, main


def fixture(tmp_path, content):
    csv = tmp_path / 'ekf.csv'
    csv.write_text('time_s,reference_soc_pct,estimated_soc_pct\n' + content)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 'ekf-reference-v1', 'environment': 'synthetic',
                                    'reference_source': 'unit test fixture, not measured SOC',
                                    'csv_sha256': hashlib.sha256(csv.read_bytes()).hexdigest()}))
    return csv, manifest


def test_ekf_error_units_and_hash(tmp_path):
    csv, manifest = fixture(tmp_path, '0,50,53\n1,50,46\n')
    _, result = ekf_data(csv, manifest)
    assert result['rmse_percentage_points'] == pytest.approx((25/2)**.5)
    assert result['max_absolute_error_percentage_points'] == 4
    assert result['official_acceptance'] is False
    csv.write_text(csv.read_text() + '2,50,50\n')
    with pytest.raises(ValueError, match='hash'):
        ekf_data(csv, manifest)


@pytest.mark.parametrize('content', ['0,50,nan\n1,50,50\n', '0,101,50\n1,50,50\n',
                                    '1,50,50\n0,50,50\n', '0,50,50\n0,50,50\n', '0,50,50\n'])
def test_invalid_ekf_samples(tmp_path, content):
    with pytest.raises(ValueError):
        ekf_data(*fixture(tmp_path, content))


def test_headless_ekf_render_and_no_overwrite(tmp_path):
    pytest.importorskip('matplotlib')
    csv, manifest = fixture(tmp_path, '0,50,53\n1,50,46\n')
    args = ['ekf', '--csv', str(csv), '--manifest', str(manifest), '--output-dir', str(tmp_path / 'plots')]
    assert main(args) == 0
    assert (tmp_path / 'plots/ekf_error.png').read_bytes().startswith(b'\x89PNG')
    assert main(args) == 2
