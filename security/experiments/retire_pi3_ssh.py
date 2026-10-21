"""Preview/apply removal of only the obsolete Pi3 capstone_experiment SSH key.

Run the controller on PC after independent PC-to-all-three SSH works. No SecOC,
repository, Python environment, result directory or unrelated SSH key is removed.
"""
import argparse
import hashlib
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def public_identity(text):
    parts=text.strip().split()
    if len(parts)!=3 or parts[0]!='ssh-ed25519' or parts[2]!='capstone-experiment':
        raise ValueError('expected the dedicated capstone-experiment Ed25519 public key')
    raw=base64.b64decode(parts[1],validate=True)
    return parts[0],parts[1],'SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')


def inspect_local(home):
    public=home/'.ssh/capstone_experiment.pub'
    private=home/'.ssh/capstone_experiment'
    if public.is_symlink() or private.is_symlink():raise ValueError('refuse symlink key files')
    text=public.read_text()
    _,_,fingerprint=public_identity(text)
    if private.exists():
        result=subprocess.run(['ssh-keygen','-lf',str(private)],check=True,capture_output=True,text=True,timeout=10)
        if fingerprint not in result.stdout.split():raise ValueError('private/public fingerprint mismatch')
    return text, fingerprint


def remove_authorization(home, public_text, apply=False):
    kind,blob,fingerprint=public_identity(public_text)
    path=home/'.ssh/authorized_keys'
    if path.is_symlink():raise ValueError('refuse symlink authorized_keys')
    if not path.exists():return {'fingerprint':fingerprint,'matching_lines':0,'applied':False}
    original=path.read_bytes()
    lines=original.splitlines(keepends=True)
    def matches(line):
        parts=line.decode().strip().split()
        return any(parts[i]==kind and parts[i+1]==blob for i in range(len(parts)-1))
    remaining=[line for line in lines if not matches(line)]
    count=len(lines)-len(remaining)
    result={'fingerprint':fingerprint,'matching_lines':count,'applied':False}
    if apply and count:
        stamp=str(time.time_ns())
        backup=path.with_name('authorized_keys.before-capstone-retire-'+stamp)
        with backup.open('xb') as stream:stream.write(original)
        os.chmod(backup,0o600)
        temporary=path.with_name('authorized_keys.capstone-'+stamp)
        with temporary.open('xb') as stream:stream.write(b''.join(remaining))
        os.chmod(temporary,path.stat().st_mode & 0o777)
        if path.read_bytes()!=original:
            temporary.unlink();raise ValueError('authorized_keys changed during cleanup; retry inspection')
        temporary.replace(path)
        result.update(applied=True,backup=str(backup))
    return result


def remove_key(home, public_text, apply=False):
    actual,fingerprint=inspect_local(home)
    if public_identity(actual)[:2]!=public_identity(public_text)[:2]:raise ValueError('key changed since preview')
    if apply:
        (home/'.ssh/capstone_experiment').unlink(missing_ok=True)
        (home/'.ssh/capstone_experiment.pub').unlink()
    return {'fingerprint':fingerprint,'key_files':2,'applied':apply}


def remote(settings,role,request):
    command=settings['cleanup_'+role]
    result=subprocess.run(command,input=json.dumps(request)+'\n',capture_output=True,text=True,timeout=30,check=True)
    return json.loads(result.stdout)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--remote',choices=('inspect','authorized','key'))
    args=parser.parse_args(argv)
    if args.remote:
        if args.remote=='inspect':
            public,fingerprint=inspect_local(Path.home())
            result={'public_key':public,'fingerprint':fingerprint}
        else:
            request=json.loads(sys.stdin.readline())
            operation=remove_authorization if args.remote=='authorized' else remove_key
            result=operation(Path.home(),request['public_key'],request.get('apply',False))
        print(json.dumps(result));return 0
    if not args.settings:parser.error('--settings required on PC')
    settings=json.loads(Path(args.settings).read_text())
    from security.experiments.pc_campaign import validate_pc_settings
    from security.experiments.validate_m5_settings import ssh_target
    targets=validate_pc_settings(settings)
    for role,target in (('a',targets['ecu']),('b',targets['receiver_on']),('c',targets['attacker'])):
        command=settings['cleanup_'+role]
        if command[0]!='ssh' or ssh_target(command)!=target or 'REPLACE_' in ' '.join(command):
            raise ValueError('cleanup command must address the matching node from PC')
    # Inspect C and dry-run A/B before mutation. These calls themselves prove PC SSH access.
    inspect_command=list(settings['cleanup_c'])
    inspect_command[-1]=inspect_command[-1].replace('--remote key','--remote inspect')
    evidence=json.loads(subprocess.run(inspect_command,capture_output=True,text=True,check=True,timeout=30).stdout)
    request={'public_key':evidence['public_key'],'apply':False}
    # Refuse to revoke the very identity used by PC for management.
    for role in ('a','b','c'):
        command=settings['cleanup_'+role]
        if '-i' not in command:raise ValueError('explicit independent PC SSH identity (-i) required')
        identity=Path(command[command.index('-i')+1]).expanduser()
        info=subprocess.run(['ssh-keygen','-lf',str(identity)],check=True,capture_output=True,text=True,timeout=10)
        if evidence['fingerprint'] in info.stdout.split():raise ValueError('PC must use its own key, not the retired Pi3 key')
    report={role:remote(settings,role,request) for role in ('a','b','c')}
    if args.apply:
        request['apply']=True
        for role in ('a','b'):report[role]=remote(settings,role,request)
        # Recheck PC access to both nodes before deleting C's local private/public files.
        request['apply']=False
        for role in ('a','b'):remote(settings,role,request)
        request['apply']=True
        report['c']=remote(settings,'c',request)
    print(json.dumps({'mode':'APPLY' if args.apply else 'PREVIEW','nodes':report},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
