#!/usr/bin/env python3
"""Read-only Pi environment evidence; never reads key contents or changes CAN."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import time


def command(argv):
    try:
        result=subprocess.run(argv,text=True,capture_output=True,timeout=10)
        return {'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    except (OSError,subprocess.TimeoutExpired) as error:
        return {'exit_code':None,'stdout':'','stderr':str(error)}


def key_metadata(path):
    try:
        stat=path.stat()
        return {'path':str(path),'size_bytes':stat.st_size,'mode':oct(stat.st_mode&0o777),
                'uid':stat.st_uid,'gid':stat.st_gid,'readable_by_this_user':os.access(path,os.R_OK)}
    except OSError as error:
        return {'path':str(path),'error':str(error)}


def collect(role,key_path):
    report={'schema':'pi-preflight-v1','role':role,'epoch_ns':time.time_ns(),
            'os':platform.platform(),'architecture':platform.machine(),
            'python':platform.python_version(),'key_metadata':key_metadata(Path(key_path)),
            'display':{name:os.environ.get(name) for name in
                       ('DISPLAY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_RUNTIME_DIR')},
            'commands':{}}
    commands={
        'can0':['ip','-details','-statistics','link','show','can0'],
        'cmake':['cmake','--version'], 'compiler':['c++','--version'],
        'qt':['pkg-config','--modversion','Qt6Core','Qt6Quick','Qt6QuickControls2'],
        'os_release':['cat','/etc/os-release'],
        'related_processes':['pgrep','-af','adaptive_ecu|ads1115_can_smoke|ivi_dashboard|security.ids.runtime|security.attack_simulator|security.experiments.normal_sender'],
    }
    for name,argv in commands.items():report['commands'][name]=command(argv)
    report['commands']['python_packages']=command([os.sys.executable,'-c',
        "import importlib.metadata as m,json; names=('numpy','scikit-learn','pytest'); "
        "print(json.dumps({n:m.version(n) for n in names}))"])
    if role=='ecu':report['i2c_device_exists']=Path('/dev/i2c-1').exists()
    # This is collection completeness, NOT a hardware readiness verdict.
    report['status']='COLLECTED'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('ecu','ivi'),required=True)
    parser.add_argument('--key',required=True,help='existing key path; contents are never read')
    parser.add_argument('--output',required=True,help='new JSON path')
    args=parser.parse_args()
    try:
        with Path(args.output).open('x',encoding='utf-8') as output:
            json.dump(collect(args.role,args.key),output,indent=2)
        print(json.dumps({'status':'COLLECTED','output':args.output,
                          'note':'command failures are preserved; not a PASS verdict'}))
        return 0
    except OSError as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
