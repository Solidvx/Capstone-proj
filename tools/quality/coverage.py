"""GCC JSON coverage gate, including objects with no execution data."""
import argparse
import gzip
import json
from pathlib import Path
import re
import subprocess


def product_files(root, component):
    patterns = ('src/**/*.cpp', 'tools/*.cpp', 'main.cpp') if component == 'ecu' else (
        'hal/*.cpp', 'service/*.cpp', 'ui_qml/*.cpp')
    return {str(p.relative_to(root)) for pattern in patterns for p in root.glob(pattern)}


def aggregate(documents, root, component, inventory):
    lines, branches, branch_details = {}, {}, {}
    for data in documents:
        if data.get('format_version') not in ('1', '2') or not isinstance(data.get('files'), list):
            raise ValueError('unsupported gcov JSON')
        for entry in data['files']:
            path = Path(entry['file'])
            if not path.is_absolute():
                path = Path(data['current_working_directory']) / path
            try:
                name = str(path.resolve().relative_to(root))
            except ValueError:
                continue
            allowed = ('src/', 'include/', 'tools/') if component == 'ecu' else ('hal/', 'service/', 'ui_qml/')
            if name != 'main.cpp' and not name.startswith(allowed):
                continue
            for row in entry['lines']:
                key = (name, row['line_number'])
                lines[key] = lines.get(key, False) or row['count'] > 0
                if name == 'src/app/failsafe_sm.cpp':
                    for index, branch in enumerate(row.get('branches', [])):
                        branch_key = (*key, row.get('function_name'), index)
                        branches[branch_key] = branches.get(branch_key, False) or branch['count'] > 0
                        branch_details[branch_key]={'file':name,'line':row['line_number'],
                            'function':row.get('function_name'),'index':index,
                            'throw':branch.get('throw'),
                            'source_block_id':branch.get('source_block_id'),
                            'destination_block_id':branch.get('destination_block_id')}
    present = {key[0] for key in lines}
    missing = sorted(inventory - present)
    if not inventory or not lines or missing:
        raise ValueError(f'empty or incomplete product denominator: {missing}')
    if component == 'ecu' and not branches:
        raise ValueError('missing Fail-safe branch denominator')
    def metric(values):
        return {'covered': sum(values), 'total': len(values),
                'percent': 100 * sum(values) / len(values) if values else None}
    line_metric = metric(list(lines.values()))
    branch_metric = metric(list(branches.values())) if component == 'ecu' else None
    passed = line_metric['percent'] >= 80 and (branch_metric is None or branch_metric['percent'] == 100)
    return {'status': 'PASS' if passed else 'FAIL', 'component': component,
            'lines': line_metric, 'failsafe_branches': branch_metric,
            'uncovered_failsafe_branches':[branch_details[key] for key,covered in branches.items() if not covered],
            'missing_cpp': missing, 'per_file': [
                {'file': name, **metric([v for key, v in lines.items() if key[0] == name])}
                for name in sorted(present)],
            'scope': 'Product source/header line union; zero-execution objects included. Tests, generated/system files excluded; exception branches included. QML/Python not counted.'}


def collect(build, root, component, output):
    objects = sorted(build.rglob('*.gcno'))
    if not objects:
        raise ValueError('no gcno files; build with coverage first')
    output.mkdir(parents=True, exist_ok=False)
    documents = []
    version = subprocess.check_output(['gcov', '--version'], text=True).splitlines()[0]
    for index, obj in enumerate(objects):
        dest = output / f'object-{index:04d}'
        dest.mkdir()
        proc = subprocess.run(['gcov', '-b', '-j', str(obj)], cwd=dest, text=True, capture_output=True)
        (dest / 'command.json').write_text(json.dumps({'object': str(obj), 'exit_code': proc.returncode,
                                                      'stdout': proc.stdout, 'stderr': proc.stderr}, indent=2))
        if proc.returncode or re.search(r'mismatch|version .*prefer|stamp', proc.stderr, re.I):
            raise ValueError(f'gcov failed or mismatched: {obj}: {proc.stderr}')
        files = list(dest.glob('*.gcov.json.gz'))
        if not files:
            raise ValueError(f'gcov did not produce JSON: {obj}')
        for path in files:
            with gzip.open(path, 'rt') as handle:
                documents.append(json.load(handle))
    result = aggregate(documents, root, component, product_files(root, component))
    result.update({'gcov': version, 'build': str(build), 'source': str(root), 'objects': len(objects)})
    (output / 'coverage.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--component', choices=('ecu', 'ivi'), required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    try:
        result = collect(args.build.resolve(), args.source.resolve(), args.component, args.output_dir.resolve())
        print(json.dumps({k: v for k, v in result.items() if k != 'per_file'}))
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'INVALID', 'reason': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
