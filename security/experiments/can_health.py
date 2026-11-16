"""Check a dedicated test CAN interface; optionally reset only a failed interface."""
import argparse
import json
import re
import subprocess

from security.experiments.can_capture import inspect_interface


def check(channel, recover=False,environment='physical'):
    if environment=='vcan':
        if recover or not re.fullmatch(r'vcan[0-9]+',channel):raise ValueError('read-only explicit vcan check required')
        return {'result':'CAN_HEALTHY','interface':channel,'reset':False,**inspect_interface(channel,'vcan')}
    if environment!='physical':raise ValueError('explicit bus environment required')
    if not re.fullmatch(r'can[0-9]+', channel):
        raise ValueError('physical can interface required')
    response = subprocess.run(['ip', '-details', '-json', 'link', 'show', 'dev', channel],
                              check=True, capture_output=True, text=True, timeout=10)
    entries = json.loads(response.stdout)
    if len(entries) != 1:
        raise ValueError('expected one interface')
    entry = entries[0]
    data = entry.get('linkinfo', {}).get('info_data', {})
    if entry.get('linkinfo', {}).get('info_kind') != 'can':
        raise ValueError('physical CAN required')
    if data.get('bittiming', {}).get('bitrate') != 500000:
        raise ValueError('bitrate mismatch; configure manually')
    mode = data.get('ctrlmode', [])
    if 'LOOPBACK' in mode or 'LISTEN-ONLY' in mode:
        raise ValueError('test/receive-only controller mode; configure manually')
    changed = False
    if 'UP' not in entry.get('flags', []) or data.get('state') != 'ERROR-ACTIVE':
        if not recover:
            raise RuntimeError('CAN not healthy')
        subprocess.run(['ip', 'link', 'set', channel, 'down'], check=True, timeout=10)
        subprocess.run(['ip', 'link', 'set', channel, 'type', 'can', 'bitrate', '500000',
                        'listen-only', 'off', 'loopback', 'off', 'restart-ms', '0'], check=True, timeout=10)
        subprocess.run(['ip', 'link', 'set', channel, 'up'], check=True, timeout=10)
        changed = True
    info = inspect_interface(channel, 'physical')
    if info['state'] != 'ERROR-ACTIVE' or info['bitrate'] != 500000:
        raise RuntimeError('CAN recovery failed')
    return {'result': 'CAN_HEALTHY', 'interface': channel, 'reset': changed, **info}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='can0')
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--environment',choices=('physical','vcan'),default='physical')
    args = parser.parse_args()
    print(json.dumps(check(args.interface, args.recover,args.environment)), flush=True)


if __name__ == '__main__':
    main()
