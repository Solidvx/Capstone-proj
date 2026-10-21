"""Verify report tables against preserved publication data and local references.

Run from any directory with Python standard library. --populate only replaces
the four explicitly generated table blocks; it never rewrites experiment data.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'docs/development/experiments'
FORMAL = BASE / 'physical-ablation-formal-2026-10-04'
REPORT = BASE / '최종실험_결과_보고서.md'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(headers, rows):
    return '\n'.join('| ' + ' | '.join(map(str, row)) + ' |'
                     for row in [headers, ['---'] * len(headers), *rows])


def expected_tables(data):
    counts, delivery, latency, runs = [], [], [], []
    for case in data['cases']:
        name = f"C{case['config']} {case['attack']}"
        p, a, t = (case[k] for k in (
            'primary_first_attempts', 'all_attempts', 'timing_eligible_primary_subset'))
        counts.append([name, case['plan']['recorded'], f"{p['valid']}/{p['invalid']}",
                       a['attempts'], f"{a['valid']}/{a['invalid']}", len(case['plan']['retries'])])
        n, d = t['normal_delivered_recorded'], t['normal_expected_recorded']
        success = (f"{p['reference_success_numerator']}/{p['reference_success_denominator']}"
                   if p['reference_success_denominator'] else 'N/A')
        delivery.append([name, f'{n:,}/{d:,}', f'{100*n/d:.4f}%',
                         f"{p['attack_published']:,}", success])
        if case['config'] == 3:
            latency.append([case['attack'],
                            f"{p['reference_detected']}/{p['reference_detection_denominator']}",
                            p['invalid'], t['detected_latency_samples'],
                            *[f"{t[k]:.4f}" for k in (
                                'detected_latency_mean_ms', 'detected_latency_p95_ms',
                                'detected_latency_max_ms')]])
    for run in sorted(data['runs'], key=lambda x: x['run_id']):
        rid, m = run['run_id'], run['metrics']
        link = f'physical-ablation-formal-2026-10-04/publication/runs/{rid}/summary.json'
        runs.append([f'[{rid}]({link})', f"{m['valid']}/{m['invalid']}",
                     '지연·전달률 제외' if run.get('exception', {}).get('exclude_timing') else '원본 정책 참조'])
    return {
        'counts': table(['조건', '기록한 계획 번호', '최초 VALID/INVALID', '전체 시도',
                         '전체 VALID/INVALID', '추가 재시도'], counts),
        'delivery': table(['조건', '정상 전달/기대', '정상 전달률', '주입 게시 수',
                           '참조 성공 시행/측정 시행'], delivery),
        'latency': table(['공격', '탐지/유효 시행', 'INVALID', '지연 표본',
                          '평균 ms', 'p95 ms', '최대 ms'], latency),
        'runs': table(['run ID·근거', '전체 VALID/INVALID', '계측 해석'], runs),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--populate', action='store_true')
    args = parser.parse_args()
    summary_path = FORMAL / 'publication/summary.json'
    data = read_json(summary_path)
    content = REPORT.read_text(encoding='utf-8-sig')
    expected = expected_tables(data)
    errors = []
    for name, value in expected.items():
        pattern = rf'(<!-- GENERATED:{name}:BEGIN -->).*?(<!-- GENERATED:{name}:END -->)'
        match = re.search(pattern, content, re.S)
        if not match:
            errors.append(f'missing block {name}')
            continue
        replacement = match[1] + '\n' + value + '\n' + match[2]
        if args.populate:
            content = content[:match.start()] + replacement + content[match.end():]
        elif match[0] != replacement:
            errors.append(f'numeric table mismatch {name}')
    if args.populate:
        REPORT.write_text(content, encoding='utf-8', newline='\n')

    totals = {k: sum(c['primary_first_attempts'][k] for c in data['cases'])
              for k in ('attempts', 'valid', 'invalid')}
    if totals != dict(attempts=1200, valid=1196, invalid=4):
        errors.append(f'narrative primary totals drift: {totals}')
    if sum(c['all_attempts']['attempts'] for c in data['cases']) != 1201:
        errors.append('all attempt total drift')
    if any(c['primary_first_attempts']['if_events'] for c in data['cases']):
        errors.append('IF event claim drift')
    integration = BASE / 'ecu-ivi-integration-2026-10-03_04/analysis'
    perf = read_json(integration / 'perf-formal-002-analysis.json')
    for key in ('mean_ms', 'max_ms', 'p99_ms'):
        if f"{perf['intervals']['T1-T4'][key]:.6f}ms" not in content:
            errors.append(f'performance number missing: {key}')
    normal = read_json(integration / 'normal-if-20261004-064946.json')
    for row in normal['results']:
        ratio = f"{row['false_positive_windows']}/{row['complete_windows']}"
        if ratio not in content:
            errors.append(f'FPR denominator missing: {ratio}')

    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', content)
    for link in links:
        if re.match(r'\w+://', link):
            continue
        path, _, anchor = unquote(link).partition('#')
        target = (REPORT.parent / path).resolve() if path else REPORT
        if not target.exists():
            errors.append(f'broken link: {link}')
        elif anchor and f'id="{anchor}"' not in target.read_text(encoding='utf-8-sig'):
            errors.append(f'missing explicit anchor: {link}')
    if content.count('```') % 2:
        errors.append('unbalanced code fences')
    if '\ufffd' in content or '???' in content:
        errors.append('encoding corruption')
    columns = None
    for line in content.splitlines():
        if line.startswith('|'):
            count = line.count('|')
            if columns is not None and count != columns:
                errors.append('table column mismatch: ' + line[:100])
            columns = count
        else:
            columns = None
    requirements = (ROOT / 'docs/SRS.md').read_text(encoding='utf-8-sig')
    tests = (ROOT / 'docs/TEST_PLAN.md').read_text(encoding='utf-8-sig')
    for ident in set(re.findall(r'(?:NFR|TC)-[A-Z]+-\d{3}', content)):
        if ident not in (requirements if ident.startswith('NFR') else tests):
            errors.append('unknown requirement/test: ' + ident)
    result = dict(status='PASS' if not errors else 'FAIL', errors=errors,
                  generated_tables=len(expected), cases=len(data['cases']),
                  runs=len(data['runs']), primary_totals=totals, checked_links=len(links),
                  report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                  summary_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest(),
                  scope='Tables, selected integration figures, local links, explicit anchors, IDs, encoding and structure. No hardware execution.')
    (Path(__file__).parent / 'final-report-validation.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
