#!/usr/bin/env python3
"""Package the current ECU/IVI/security sources, including uncommitted fixes.

Does not deploy, commit, configure CAN, stop services or copy SecOC keys.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import os
import subprocess
import tarfile

SOURCE_ROOTS = (
    'adaptive_ecu/include', 'adaptive_ecu/src', 'adaptive_ecu/test', 'adaptive_ecu/tools',
    'ivi_platform/hal', 'ivi_platform/service', 'ivi_platform/ui_qml', 'ivi_platform/test', 'security',
)
SUFFIXES = {'.cpp', '.h', '.py', '.qml'}
EXCLUDED = {'build', 'logs', 'models', 'data', '__pycache__', '.venv', 'venv', 'env', '.git'}
EXTRAS = (
    'adaptive_ecu/CMakeLists.txt', 'adaptive_ecu/main.cpp',
    'adaptive_ecu/data/battery_profile.csv', 'adaptive_ecu/data/failsafe_demo.csv',
    'adaptive_ecu/data/failsafe_demo.manifest.json', 'ivi_platform/CMakeLists.txt',
    'security/requirements.txt', 'ivi_platform/scripts/prepare_pi_handoff.py',
    'ivi_platform/scripts/collect_pi_preflight.py',
    'ivi_platform/scripts/analyze_period.py', 'ivi_platform/scripts/normalize_candump_period.py',
    'docs/development/playbooks/pi-manual-handoff.md',
    'docs/development/playbooks/security-can-integration.md',
    'docs/development/playbooks/m5-ablation-runner.md',
    'docs/development/playbooks/experiment-analysis.md',
    'security/experiments/m5-settings.template.json',
    'security/experiments/ids-captures.template.json', '임시_할일.md',
    'security/ids/README.md', 'security/ids/how_to_train.md',
    'docs/development/playbooks/pre-hardware-readiness.md',
    'docs/ICD.md', 'docs/SRS.md', 'docs/TEST_PLAN.md',
)


def selected_files(root):
    files=set(EXTRAS)
    for directory in SOURCE_ROOTS:
        for current, directories, names in os.walk(root/directory, followlinks=False):
            directories[:]=[name for name in directories if name not in EXCLUDED and
                not name.startswith('.') and not name.startswith('build') and not (Path(current)/name).is_symlink()]
            for name in names:
                path=Path(current)/name
                if path.suffix in SUFFIXES and not name.startswith('.'):
                    files.add(path.relative_to(root).as_posix())
    for name in files:
        path=root/name
        if path.is_symlink() or not path.is_file() or root.resolve() not in path.resolve().parents:
            raise ValueError(f'missing or unsafe input: {name}')
    return sorted(files)


def create_bundle(root,output):
    files=selected_files(root)
    output.mkdir(parents=True,exist_ok=False)
    manifest={'schema':'pi-source-handoff-v1','kind':'WORKTREE-SNAPSHOT-NOT-COMMIT',
              'files':{},'excluded':'keys, credentials, env files, builds, models, raw logs'}
    try:
        manifest['base_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        manifest['base_commit']=None
    archive=output/'capstone-pi-handoff.tar.gz'
    # Read/hash/add exactly the same bytes, even if the worktree changes during packing.
    with tarfile.open(archive,'x:gz') as package:
        for name in files:
            path=root/name;data=path.read_bytes()
            manifest['files'][name]=hashlib.sha256(data).hexdigest()
            member=tarfile.TarInfo('Capstone-handoff/'+name)
            member.size=len(data);member.mode=0o755 if path.stat().st_mode&0o111 else 0o644
            package.addfile(member,io.BytesIO(data))
        checksums=''.join(f'{digest}  {name}\n' for name,digest in manifest['files'].items()).encode('utf-8')
        member=tarfile.TarInfo('Capstone-handoff/HANDOFF-FILES.sha256');member.size=len(checksums);member.mode=0o644
        package.addfile(member,io.BytesIO(checksums))
        data=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
        member=tarfile.TarInfo('Capstone-handoff/HANDOFF-MANIFEST.json');member.size=len(data);member.mode=0o644
        package.addfile(member,io.BytesIO(data))
    (output/'HANDOFF-MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'capstone-pi-handoff.tar.gz.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    (output/'files.sha256').write_text(''.join(f'{digest}  {name}\n' for name,digest in manifest['files'].items()),encoding='utf-8')
    return {'archive':str(archive),'sha256':digest,'source_files':len(files)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    try:
        print(json.dumps(create_bundle(root,Path(args.output_dir)),sort_keys=True))
        return 0
    except (OSError,ValueError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
