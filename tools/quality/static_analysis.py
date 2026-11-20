"""Run cppcheck on explicit product files and fail on Error severity only."""
import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def evaluate(xml, returncode, source_count):
    if source_count <= 0 or returncode not in (0, 2):
        raise ValueError('empty analysis or tool execution failure')
    root = ET.fromstring(xml)
    if root.tag != 'results' or root.find('cppcheck') is None or root.find('errors') is None:
        raise ValueError('invalid cppcheck report')
    findings = []
    for item in root.findall('./errors/error'):
        severity = item.get('severity')
        if severity not in ('error', 'warning', 'style', 'performance', 'portability', 'information', 'debug'):
            raise ValueError('unknown severity')
        findings.append({'id': item.get('id'), 'severity': severity, 'message': item.get('msg'),
                         'locations': [node.attrib for node in item.findall('location')]})
    # cppcheck uses exit code 2 for any configured finding, including warnings.
    if returncode == 2 and not findings:
        raise ValueError('tool failed without a diagnostic')
    count = sum(x['severity'] == 'error' for x in findings)
    return {'status': 'FAIL' if count else 'PASS', 'errors': count,
            'source_count': source_count, 'findings': findings}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path('.'))
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    repo = args.repo.resolve()
    patterns = ('adaptive_ecu/src/**/*.cpp', 'adaptive_ecu/main.cpp', 'adaptive_ecu/tools/*.cpp',
                'ivi_platform/hal/*.cpp', 'ivi_platform/service/*.cpp', 'ivi_platform/ui_qml/*.cpp')
    sources = sorted({str(path) for pattern in patterns for path in repo.glob(pattern)})
    try:
        if not sources:
            raise ValueError('no product sources')
        args.output_dir.mkdir(parents=True, exist_ok=False)
        includes = ['adaptive_ecu/include', 'common', 'ivi_platform/hal', 'ivi_platform/service', 'ivi_platform/ui_qml']
        cmd = ['cppcheck', '--std=c++17', '--language=c++', '--enable=warning,style,performance,portability',
               '--xml', '--xml-version=2', '--error-exitcode=2', '--suppress=missingIncludeSystem',
               '-DQ_OBJECT=', '-DQ_PROPERTY(...)=', '-DQ_INVOKABLE=', '-Dsignals=public', '-Dslots=',
               *['-I' + str(repo / d) for d in includes], *sources]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        (args.output_dir / 'cppcheck.xml').write_text(proc.stderr)
        (args.output_dir / 'stdout.txt').write_text(proc.stdout)
        result = evaluate(proc.stderr, proc.returncode, len(sources))
        result['version'] = subprocess.check_output(['cppcheck', '--version'], text=True).strip()
        (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'findings'}))
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'INVALID', 'reason': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
