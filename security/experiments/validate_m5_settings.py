"""Read-only static command validation; no SSH, CAN, sudo or process launch."""
import argparse
import json
from pathlib import Path
import re

ROLES=('observer','receiver_on','receiver_off','normal_sender','ids')
VALUES={'run_id':'VALIDATION-ONLY','secoc':'on','lifetime_s':'60','lifetime_ms':'60000'}


def ssh_target(command):
    index=1
    with_value={'-o','-p','-i','-F','-J','-l','-b'}
    flags={'-T','-t','-tt','-n','-q','-4','-6','-v','-vv','-vvv'}
    while index<len(command):
        value=command[index]
        if value in with_value:index+=2
        elif value in flags:index+=1
        elif value.startswith('-'):raise ValueError('unsupported SSH option; use explicit option/value form')
        else:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+',value):
                raise ValueError('SSH target must be USER@HOST')
            if index+1>=len(command):raise ValueError('missing remote command')
            return value
    raise ValueError('missing SSH target')


def validate(settings,environment):
    if environment not in ('vcan','physical-can'):raise ValueError('invalid environment')
    if not isinstance(settings,dict):raise ValueError('settings must be an object')
    targets=[]
    for role in ROLES:
        command=settings.get(role)
        if not isinstance(command,list) or not command or any(not isinstance(v,str) or not v.strip() for v in command):
            raise ValueError(f'{role}: nonempty argv array required')
        if any('REPLACE_' in v for v in command):raise ValueError(f'{role}: unresolved REPLACE marker')
        try:
            for value in command:value.format_map(VALUES)
        except (ValueError,KeyError) as error:raise ValueError(f'{role}: invalid runtime placeholder') from error
        if not any('{run_id}' in v for v in command):raise ValueError(f'{role}: shared run_id missing')
        if Path(command[0]).name=='ssh':
            if not any('{lifetime_' in v for v in command):raise ValueError(f'{role}: bounded remote lifetime missing')
            target=ssh_target(command)
            if role in ('observer','receiver_on','receiver_off'):targets.append(target)
        elif environment=='physical-can' and role in ('observer','receiver_on','receiver_off'):
            raise ValueError(f'{role}: physical Node B command must use SSH')
    if environment=='physical-can':
        if settings.get('observer_receiver_same_node') is not True or len(set(targets))!=1:
            raise ValueError('observer/receivers must explicitly share the same Node B SSH target')
    return {'status':'STATIC_VALID','environment':environment,
            'note':'Does not prove connectivity, key equality, clock co-location, permissions or hardware readiness.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',required=True)
    parser.add_argument('--environment',choices=('vcan','physical-can'),required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(validate(json.loads(Path(args.settings).read_text()),args.environment)));return 0
    except (OSError,ValueError,TypeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
