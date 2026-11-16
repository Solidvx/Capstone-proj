"""R03 same-IVI-clock response metric; not physical TX latency or UI rendering."""
import re

from security.can_diagnostic import valid_body
from security.experiments.session_campaign_evidence import integer, number, signature

UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def replay_start(*, frames, signatures, rejections, diagnostics, run_id, clock, baseline, exposure, end):
    """First repeated auth observed by IVI, independently proven MAC-valid replay.

    This is the first identifiable replay authentication, not the raw/TX start.
    No witness, prior original, stable context or pair match means no timestamp.
    """
    sessions = {row['session_id'] for _, row, _ in diagnostics}
    if len(sessions) != 1:
        return None
    context = bytes.fromhex(next(iter(sessions)))
    arrivals = []
    for row in rejections:
        if row.get('result') != 'LOCAL_REJECTION_RECORD':
            continue
        body = bytes.fromhex(row['body_hex'])
        if not valid_body(0x303, 5, body) or body[32:36] != bytes((7, 1, 1, 0)):
            continue
        if row.get('run_id') != run_id or row.get('clock_id') != clock:
            continue
        recorded = integer(row['recorded_monotonic_ns']) / 1e9
        if not exposure <= recorded < end:
            continue
        ref = body[36:80]
        if ref[12:28] != context or ref[:4] != bytes((2, 8, 8, 0)):
            continue
        original = (int.from_bytes(ref[4:8], 'big'), ref[28:36].hex())
        auth = (int.from_bytes(ref[8:12], 'big'), ref[36:44].hex())
        if original not in signatures or auth not in signatures:
            continue
        originals = [r for r in rejections if r.get('result') == 'SESSION_PUBLICATION'
            and r.get('run_id') == run_id and r.get('clock_id') == clock
            and r.get('secoc_verified') is True and r.get('valid') is True and r.get('stale') is False
            and r.get('bms_context_id') == context.hex()
            and r.get('bms_raw_hex') == original[1] and r.get('bms_auth_hex') == auth[1]
            and baseline <= integer(r['bms_auth_received_ns']) / 1e9 < end
            and integer(r['t1_received_ns']) <= integer(r['t2_published_ns'])
            and integer(r['bms_auth_received_ns']) <= integer(r['t2_published_ns'])]
        if not originals:
            continue
        raw_times = [number(f['t']) for f in frames if signature(f) == original]
        auth_times = [number(f['t']) for f in frames if signature(f) == auth]
        # A prior raw/auth observation is needed; a lone rejected copy is not
        # enough to date the first observed repetition independently.
        for index, stamp in enumerate(auth_times):
            if stamp < exposure:
                continue
            if any(prior < stamp and any(0 <= prior - raw <= .1 for raw in raw_times)
                   for prior in auth_times[:index]):
                # If the first repetition predates original publication, do not
                # choose a later copy to manufacture a smaller response time.
                if any(integer(r['t2_published_ns']) / 1e9 < stamp for r in originals):
                    arrivals.append(stamp)
                break
    return min(arrivals) if arrivals else None


def measure(*, attack, code, run_id, signatures, observer, window, diagnostics, accepted, valid,
            rejections=()):
    result = {'definition': 'ivi-observation-to-semantic-incident-v1', 'status': 'INVALID',
              'target_s': 3., 'latency_s': None, 'start_ns': None, 'end_ns': None,
              'incident_id': None, 'clock_id': None, 'reason': None,
              'screen_render_evaluated': False, 'start_basis': 'FIRST_UNIQUE_ATTACK_OBSERVATION'}
    def stop(status, reason):
        result.update(status=status, reason=reason)
        return result
    if not valid:
        return stop('INVALID', 'TRIAL_EVIDENCE_INVALID')
    try:
        baseline, exposure, _post, end = window
        clocks = {row.get('clock_id') for row in observer if row.get('result') == 'PHASE'}
        if len(clocks) != 1 or not all(isinstance(c, str) and UUID.fullmatch(c) for c in clocks):
            return stop('INVALID', 'IVI_CLOCK_ID_UNVERIFIED')
        clock = next(iter(clocks)); result['clock_id'] = clock
        frames = [row for row in observer if row.get('result') == 'OBS_FRAME'
                  and baseline <= number(row['t']) < end]
        if any(signature(row) in signatures and (row.get('extended', False) or row.get('remote', False)
                or row.get('error', False) or ('dlc' in row and integer(row['dlc']) != len(bytes.fromhex(row['data']))))
               for row in frames):
            return stop('INVALID', 'ATTACK_FRAME_METADATA_UNVERIFIED')
        if attack == 'replay':
            result['start_basis'] = 'FIRST_REPEATED_AUTH_WITH_VERIFIED_REJECTION'
            if any(number(b['t']) < number(a['t']) for a, b in zip(frames, frames[1:])):
                return stop('INVALID', 'IVI_OBSERVER_TIME_ORDER_INVALID')
            stamp = replay_start(frames=frames, signatures=signatures, rejections=rejections,
                diagnostics=diagnostics, run_id=run_id, clock=clock, baseline=baseline, exposure=exposure, end=end)
            if stamp is None:
                return stop('UNMEASURABLE', 'AMBIGUOUS_ATTACK_START')
            arrivals = [stamp]
        else:
            if any(signature(row) in signatures for row in frames if number(row['t']) < exposure):
                return stop('UNMEASURABLE', 'AMBIGUOUS_ATTACK_START')
            arrivals = [number(row['t']) for row in frames if number(row['t']) >= exposure and signature(row) in signatures]
        if not arrivals:
            return stop('INVALID', 'NO_IVI_ATTACK_OBSERVATION')
        start = round(min(arrivals) * 1e9); result['start_ns'] = start
        prior = {body[16:32] for received, row, body in diagnostics
                 if row['kind'] == 4 and body[32] == code and received < exposure}
        endpoints = []
        ambiguous = False
        for received, row, body in diagnostics:
            if row['kind'] != 4 or body[32] != code or body[33] != 1 or received < exposure:
                continue
            if body[16:32] in prior:
                ambiguous = True
                continue
            if row.get('incident_semantic_accepted') is not True:
                continue
            if row.get('run_id') != run_id or row.get('clock_id') != clock:
                return stop('INVALID', 'INCIDENT_RUN_OR_CLOCK_UNVERIFIED')
            if (4, row['body_hex']) not in accepted:
                return stop('INVALID', 'INCIDENT_IPC_LINK_UNVERIFIED')
            stamp = integer(row['semantic_verified_monotonic_ns'])
            if stamp < integer(row['verified_monotonic_ms']) * 1000000 or stamp < start:
                return stop('INVALID', 'INCIDENT_CLOCK_ORDER_INVALID')
            if stamp < round(end * 1e9):
                endpoints.append((stamp, body[16:32].hex()))
        if not endpoints:
            if ambiguous:
                return stop('UNMEASURABLE', 'PREEXISTING_INCIDENT')
            if end - start / 1e9 < 3:
                return stop('INVALID', 'INCOMPLETE_RESPONSE_WINDOW')
            return stop('MISSED', 'NO_NEW_SEMANTIC_INCIDENT')
        stamp, identity = min(endpoints)
        result.update(end_ns=stamp, incident_id=identity, latency_s=(stamp-start)/1e9)
        return stop('PASS' if stamp-start <= 3000000000 else 'FAIL',
                    'WITHIN_TARGET' if stamp-start <= 3000000000 else 'OVER_TARGET')
    except (ValueError, KeyError, TypeError, OverflowError):
        return stop('INVALID', 'MALFORMED_RESPONSE_EVIDENCE')
