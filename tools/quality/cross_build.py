"""Build both ARM64 products on x86-64 and run all non-CAN C++ tests via QEMU.

Native quality.yml still owns the complete Python/real-vcan/coverage gates.
This does not deploy or weaken those gates, and never uses a physical bus.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

try:
    from .ctest_gate import EXPECTED, validate_names
except ImportError:  # Direct CLI invocation from the read-only source mount.
    from ctest_gate import EXPECTED, validate_names

EXCLUDED = {
    'ecu': {'soc_profile_product': 'Python native integration gate',
            'physical_capture_cli': 'Python/Linux file and process integration gate',
            'bounded_sensor_read': 'Linux native fork/waitpid/owner-death lifecycle gate',
            'physical_sensor_runtime': 'Native spawn/exec/Python IPC and owned-process lifecycle gate',
            'physical_ecu_product': 'Native owned sensor worker and authenticated virtual CAN product gate',
            'can_session_vcan': 'native virtual CAN gate',
            'ecu_session_product': 'native virtual CAN product gate',
            'can_receive_lifecycle': 'native virtual CAN driver lifecycle gate'},
    'ivi': {'can_session_vcan': 'native virtual CAN gate',
            'socketcan_receiver': 'native virtual CAN receiver gate',
            'event_history_product': 'native Qt/Python/preload product gate'},
}


def elf_machine(path):
    with Path(path).open('rb') as handle:
        header = handle.read(20)
    if len(header) != 20 or header[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected little-endian ELF64: ' + str(path))
    return struct.unpack_from('<H', header, 18)[0]


def validate_results(tree, expected):
    cases = list(tree.iter('testcase'))
    names = [case.get('name') for case in cases]
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError('cross C++ test inventory differs')
    if any(case.find(kind) is not None for case in cases for kind in ('failure', 'error', 'skipped')):
        raise ValueError('cross C++ failure, error or skip')
    return len(cases)


def input_hashes(repo):
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    result = {name: sha(repo/name) for name in
        ('Dockerfile.arm64', 'toolchain-aarch64.cmake', 'tools/quality/cross_build.py',
         'tools/quality/ctest_gate.py', 'adaptive_ecu/CMakeLists.txt', 'ivi_platform/CMakeLists.txt')}
    for directory in ('adaptive_ecu', 'ivi_platform', 'common'):
        for current, folders, names in os.walk(repo/directory, followlinks=False):
            folders[:] = [name for name in folders if not name.startswith(('.', 'build')) and
                          name not in ('__pycache__', 'logs', 'models')]
            for name in names:
                path = Path(current)/name
                if path.suffix in ('.cpp', '.h', '.qml', '.py', '.csv', '.conf', '.ttf', '.tsv'):
                    if path.is_symlink():raise ValueError('symlink cross source rejected')
                    result[str(path.relative_to(repo))] = sha(path)
    return result


def run(repo, output):
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    report = {'schema': 'arm64-cross-v1', 'status': 'RUNNING', 'stages': [], 'components': {},
              'excluded_from_emulation': EXCLUDED,
              'scope': 'Both ARM64 products and all non-CAN C++ tests; native full product/Python/coverage gates remain separate.'}
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def save():
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    def command(name, argv):
        started = time.monotonic()
        log = output / (name + '.log')
        with log.open('w') as stream:
            result = subprocess.run(argv, cwd=repo, env=environment, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=1200)
        report['stages'].append({'stage': name, 'argv': argv, 'returncode': result.returncode,
                                 'seconds': time.monotonic()-started, 'log': log.name, 'sha256': sha(log)})
        save()
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect ' + str(log))
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', QT_QPA_PLATFORM='offscreen',
                       QT_QUICK_BACKEND='software', HOME='/var/tmp')
    environment.pop('CAPSTONE_SESSION_TEST_INTERFACE', None)
    save()
    try:
        compiler = shutil.which('g++')
        cross = shutil.which('aarch64-linux-gnu-g++')
        if not compiler or not cross or elf_machine(Path(compiler).resolve()) != 62:
            raise ValueError('x86-64 compiler host required; native ARM64 is not cross acceptance')
        if not subprocess.check_output([cross, '-dumpmachine'], text=True).strip().startswith('aarch64-'):
            raise ValueError('ARM64 cross compiler required')
        if not Path('/usr/bin/qemu-aarch64').is_file():
            raise ValueError('explicit QEMU interpreter required')
        report['host_compiler_machine'] = 62
        report['compiler_target'] = subprocess.check_output([cross, '-dumpmachine'], text=True).strip()
        report['qemu_version'] = subprocess.check_output(['/usr/bin/qemu-aarch64', '--version'], text=True).splitlines()[0]
        report['emulator_elf_machine'] = elf_machine('/usr/bin/qemu-aarch64')
        report['emulator_sha256'] = sha('/usr/bin/qemu-aarch64')
        report['input_sha256'] = input_hashes(repo)
        if Path('/cross-environment/packages.tsv').is_file():
            shutil.copyfile('/cross-environment/packages.tsv', output/'packages.tsv')
        for component, directory in (('ecu', 'adaptive_ecu'), ('ivi', 'ivi_platform')):
            build = output / component
            command(component+'-configure', ['cmake', '-S', str(repo/directory), '-B', str(build),
                '-DCMAKE_BUILD_TYPE=Debug', '-DCMAKE_TOOLCHAIN_FILE='+str(repo/'toolchain-aarch64.cmake')])
            command(component+'-build', ['cmake', '--build', str(build), '-j2'])
            listing = json.loads(subprocess.check_output(['ctest', '--test-dir', str(build), '--show-only=json-v1'], text=True))
            validate_names([t['name'] for t in listing['tests']], component)
            selected = {'test_'+name for name in EXPECTED[component]-EXCLUDED[component].keys()}
            for test in listing['tests']:
                if test['name'] in selected:
                    argv = test.get('command', [])
                    if argv[:3] != ['/usr/bin/qemu-aarch64', '-L', '/']:
                        raise ValueError('test is not explicitly emulated: '+test['name'])
                    if len(argv) < 4 or elf_machine(argv[3]) != 183:
                        raise ValueError('test is not ARM64: '+test['name'])
            binary = build / ('adaptive_ecu' if component == 'ecu' else 'ivi_dashboard')
            if elf_machine(binary) != 183:
                raise ValueError('product is not ARM64')
            report['components'][component] = {'binary': str(binary), 'machine': 183, 'sha256': sha(binary),
                                               'selected': sorted(selected)}
            pattern = '^('+'|'.join(re.escape(name) for name in sorted(selected))+')$'
            junit = build/'cross-junit.xml'
            command(component+'-qemu-tests', ['ctest', '--test-dir', str(build), '-R', pattern,
                    '--no-tests=error', '--output-on-failure', '--timeout', '60', '--output-junit', str(junit)])
            report['components'][component]['passed'] = validate_results(ET.parse(junit).getroot(), selected)
            report['components'][component]['junit_sha256'] = sha(junit)
        if input_hashes(repo) != report['input_sha256'] or sha('/usr/bin/qemu-aarch64') != report['emulator_sha256']:
            raise ValueError('cross inputs changed')
        report['status'] = 'PASS'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, ET.ParseError) as error:
        report.update(status='FAIL', error=str(error))
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.repo.resolve(), args.output_dir.resolve())
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
