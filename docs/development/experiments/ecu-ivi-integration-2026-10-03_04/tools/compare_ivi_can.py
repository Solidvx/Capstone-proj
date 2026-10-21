"""Read-only classical CAN/IVI log comparison; alignment is not inferred."""
import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from decimal import Decimal
from pathlib import Path


def read_can(path, mode):
    frames = []
    clock = 0
    previous = None
    for line_no, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        if mode == 'absolute':
            m = re.fullmatch(r'\s*\((\d+\.\d+)\)\s+(\S+)\s+([0-9A-Fa-f]{3})#([0-9A-Fa-f]{0,16})\s*', line)
            if not m or len(m[4]) % 2:
                raise ValueError(f'unsupported candump -L row {line_no}')
            data = m[4].lower()
        else:
            m = re.fullmatch(r'\s*\((\d+\.\d+)\)\s+(\S+)\s+([0-9A-Fa-f]{3})\s+\[8\]\s+((?:[0-9A-Fa-f]{2}\s*){8})', line)
            if not m:
                raise ValueError(f'unsupported candump -td row {line_no}')
            data = ''.join(m[4].split()).lower()
        ns = int(Decimal(m[1])*1_000_000_000)
        clock = ns if mode == 'absolute' else clock+ns
        if previous is not None and clock < previous:
            raise ValueError('CAN clock moved backwards')
        previous = clock
        frames.append((clock, m[2], int(m[3],16), data))
    if not frames:
        raise ValueError('empty CAN log')
    if len({f[1] for f in frames}) != 1:
        raise ValueError('mixed CAN interfaces')
    return frames


def compare(can_path, receiver_path, mode):
    frames = read_can(can_path, mode)
    records = [json.loads(line) for line in Path(receiver_path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    rx = [r for r in records if r.get('result') == 'FRAME']
    if not rx or len({r['run_id'] for r in rx}) != 1:
        raise ValueError('empty or mixed receiver run')
    times = [int(r['timestamp_ns']) for r in rx]
    if times != sorted(times):
        raise ValueError('receiver timestamps reversed')
    a = [(f[2],f[3]) for f in frames]
    b = [(r['can_id'],r['data'].lower()) for r in rx]
    # Compare order without automatically aligning different capture intervals.
    first = next((i for i,(x,y) in enumerate(zip(a,b)) if x != y), None)
    if first is None and len(a) != len(b):
        first = min(len(a),len(b))
    stamps = [f[0] for f in frames if f[2] == 0x100]
    periods = [(y-x)/1e6 for x,y in zip(stamps,stamps[1:])]
    counters = []
    for _,_,cid,data in frames:
        if cid == 0x102:
            raw = bytes.fromhex(data)
            if len(raw) != 8:
                raise ValueError('invalid BMS authentication DLC')
            counters.append(int.from_bytes(raw[4:],'big'))
    discontinuities = [{'pair_index':i,'previous':x,'current':y,'modulo_delta':(y-x)&0xffffffff}
                       for i,(x,y) in enumerate(zip(counters,counters[1:])) if ((y-x)&0xffffffff) != 1]
    accepted = [r for r in rx if r.get('message') == 'Authenticated BMS data published']
    soc_bad = 0
    for r in accepted:
        raw = bytes.fromhex(r['source_data'])
        if len(raw) != 8 or r['soc'] != raw[0]*.5:
            soc_bad += 1
    return {'source_sha256': {str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (can_path,receiver_path)},
            'can_frames':len(a),'receiver_frames':len(b),'other_receiver_records':len(records)-len(rx),
            'exact_sequence_match':a==b,'first_difference_index':first,
            'can_counts':dict(Counter(hex(f[2]) for f in frames)),
            'authenticated_bms_log_count':len(accepted),'soc_decode_mismatches':soc_bad,
            'receiver_messages':dict(Counter(r.get('message','') for r in rx)),
            'secoc_on_all_frames':all(r.get('secoc_on') is True for r in rx),
            'counter_discontinuities':discontinuities,
            'can_span_s':(frames[-1][0]-frames[0][0])/1e9,
            'bms_period_ms':{'count':len(periods),'mean':statistics.mean(periods) if periods else None,
                'min':min(periods) if periods else None,'max':max(periods) if periods else None,
                'outside_90_110':sum(not 90<=v<=110 for v in periods)},
            'formal_verdict':'NOT_ASSESSED',
            'limits':'Strict classical-CAN parser: unsupported/error/FD rows stop analysis, never silently dropped. No inferred capture alignment or loss rate. Different node clocks never subtracted. Counter discontinuities may indicate restart or capture gaps, not necessarily bus loss.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('can',type=Path);p.add_argument('receiver',type=Path)
    p.add_argument('--time-mode',choices=['absolute','delta'],required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    report=compare(args.can,args.receiver,args.time_mode)
    with args.out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
