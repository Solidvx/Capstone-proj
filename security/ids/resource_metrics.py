"""Opt-in bounded measurements of this IDS process, never detector decisions.

Elapsed time is the measured loop's host monotonic interval. Replay timestamps
are a different clock. RSS endpoints are not a sampled peak; ru_maxrss is the
whole process lifetime peak (including imports/training), not a loop-only peak.
"""
from contextlib import contextmanager
import math
import os
from pathlib import Path
import signal
import sys
import time
import uuid


class MeasurementTerminated(BaseException):
    """Only installed by an explicitly measured CLI run."""


class Duration:
    # Fixed measurement buckets, not detector thresholds. No sample list grows.
    upper_ns = (1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000, 1_000_000_000)

    def __init__(self):
        self.count = self.failed = self.total_ns = 0
        self.minimum_ns = self.maximum_ns = None
        self.buckets = [0] * (len(self.upper_ns) + 1)

    def add(self, elapsed, failed=False):
        if type(elapsed) is not int or elapsed < 0:
            raise ValueError('measurement clock regressed')
        self.count += 1
        self.failed += int(failed)
        self.total_ns += elapsed
        self.minimum_ns = elapsed if self.minimum_ns is None else min(self.minimum_ns, elapsed)
        self.maximum_ns = elapsed if self.maximum_ns is None else max(self.maximum_ns, elapsed)
        index = next((i for i, limit in enumerate(self.upper_ns) if elapsed <= limit), len(self.upper_ns))
        self.buckets[index] += 1

    def report(self):
        return {'calls': self.count, 'failed_calls': self.failed, 'total_ns': self.total_ns,
                'minimum_ns': self.minimum_ns, 'maximum_ns': self.maximum_ns,
                'mean_ns': self.total_ns / self.count if self.count else None,
                'histogram_upper_inclusive_ns': list(self.upper_ns) + [None],
                'histogram_counts': self.buckets.copy()}


def memory_snapshot():
    result = {'rss_bytes': None, 'rss_source': None, 'process_lifetime_peak_rss_bytes': None,
              'peak_source': None, 'unavailable': []}
    if sys.platform.startswith('linux'):
        try:
            with Path('/proc/self/status').open() as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError('oversized process status')
            row = next(line.split() for line in raw.splitlines() if line.startswith('VmRSS:'))
            if len(row) != 3 or row[2] != 'kB' or not row[1].isdigit():
                raise ValueError('invalid RSS unit')
            result.update(rss_bytes=int(row[1]) * 1024, rss_source='/proc/self/status VmRSS (kB*1024)')
        except (OSError, ValueError, StopIteration):
            result['unavailable'].append('current RSS unavailable')
    else:
        result['unavailable'].append('current RSS unsupported on this platform')
    try:
        import resource
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if not math.isfinite(raw) or raw < 0 or sys.platform not in ('linux', 'darwin'):
            raise ValueError('unknown ru_maxrss unit')
        result['process_lifetime_peak_rss_bytes'] = int(raw) * (1 if sys.platform == 'darwin' else 1024)
        result['peak_source'] = 'getrusage(RUSAGE_SELF).ru_maxrss; process lifetime including startup/training'
    except (ImportError, OSError, ValueError):
        result['unavailable'].append('process lifetime peak RSS unavailable')
    return result


class RuntimeMetrics:
    stages = ('detector_frame', 'detector_tick', 'feature_extraction', 'model_anomaly', 'model_wire_score')

    def __init__(self, run_id, protocol, source, *, clock=time.monotonic_ns,
                 cpu_clock=time.process_time_ns, memory=memory_snapshot):
        self.clock, self.cpu_clock, self.memory = clock, cpu_clock, memory
        self.run_id, self.protocol, self.source = run_id, protocol, source
        self.measurement_id = uuid.uuid4().hex
        self.durations = {name: Duration() for name in self.stages}
        self.counts = dict.fromkeys(('input_frames', 'completed_frames', 'failed_frames',
                                    'input_ticks', 'completed_ticks', 'failed_ticks',
                                    'model_evaluations', 'incomplete_model_windows', 'model_skipped',
                                    'feature_buffer_evictions', 'receive_epoch_resets', 'invalid_input_times'), 0)
        self.started_ns = self.started_cpu_ns = self.next_sample_ns = None
        self.started_memory = None
        self.first_input_time = self.last_input_time = None
        self.clock_epochs = 1
        self.socket_drops = None
        self.drop_coverage_known = source == 'live'
        self.model = {'storage': 'disabled', 'file_bytes': None, 'file_sha256': None, 'state_sha256': None}

    def start(self, model):
        if self.started_ns is not None:
            raise ValueError('measurement already started')
        self.model = model
        self.started_memory = self.memory()
        self.started_cpu_ns = self.cpu_clock()
        self.started_ns = self.clock()
        self.next_sample_ns = self.started_ns + 1_000_000_000

    @contextmanager
    def stage(self, name):
        start = self.clock()
        failed = True
        try:
            yield
            failed = False
        finally:
            self.durations[name].add(self.clock() - start, failed)

    def process(self, detector, frame, now):
        is_frame = frame is not None
        name = 'frames' if is_frame else 'ticks'
        self.counts['input_' + name] += 1
        if type(now) in (int,float) and math.isfinite(now) and now >= 0:
            if self.first_input_time is None:self.first_input_time = now
            self.last_input_time = now
        else:self.counts['invalid_input_times'] += 1
        try:
            with self.stage('detector_frame' if is_frame else 'detector_tick'):
                events = detector.observe(frame) if is_frame else detector.tick(now)
        except BaseException:
            self.counts['failed_' + name] += 1
            raise
        self.counts['completed_' + name] += 1
        for event in events:
            if event.result == 'MODEL_EVALUATION':
                self.counts['model_evaluations'] += 1
                self.counts['incomplete_model_windows'] += int(not event.input_complete)
            elif event.result == 'MODEL_SKIPPED':
                self.counts['model_skipped'] += 1
        return events

    def receive_status(self, total_socket_drops, *, reset=False):
        if type(total_socket_drops) is not int or total_socket_drops < 0:
            raise ValueError('invalid measured socket drop count')
        self.socket_drops = total_socket_drops
        if reset:
            self.counts['receive_epoch_resets'] += 1
            self.drop_coverage_known = False
            self.clock_epochs += 1

    def report(self, status, *, final=False):
        end = self.clock()
        cpu_end = self.cpu_clock()
        memory_end = self.memory()
        started = self.started_ns is not None
        elapsed = end - self.started_ns if started else None
        cpu = cpu_end - self.started_cpu_ns if started else None
        valid = started and elapsed > 0 and cpu >= 0
        seconds = elapsed / 1e9 if valid else None
        counts = self.counts.copy()
        rate = lambda count: count / seconds if seconds is not None else None
        return {
            'result': 'RESOURCE_SUMMARY' if final else 'RESOURCE_SAMPLE',
            'schema': 'ids-resource-v1', 'run_id': self.run_id,
            'measurement_id': self.measurement_id, 'pid': os.getpid(),
            'protocol': self.protocol, 'source': self.source, 'final': final,
            'status': status if valid else 'NOT_STARTED' if not started else 'INVALID_CLOCK',
            'host_monotonic_start_ns': self.started_ns, 'host_monotonic_end_ns': end,
            'elapsed_s': seconds, 'cpu_process_s': cpu / 1e9 if valid else None,
            'cpu_percent_one_core': cpu / elapsed * 100 if valid else None,
            'memory_start': self.started_memory, 'memory_end': memory_end,
            'counts': counts, 'durations': {name: value.report() for name, value in self.durations.items()},
            'rates': {'completed_frames_per_host_second': rate(counts['completed_frames']),
                      'model_windows_per_host_second': rate(counts['model_evaluations'])},
            'source_clock': {'first_input_s': self.first_input_time, 'last_input_s': self.last_input_time,
                             'epochs': self.clock_epochs, 'used_as_host_elapsed': False},
            'loss': {'observed_socket_drops': self.socket_drops,
                     'receive_coverage_known': self.drop_coverage_known,
                     'discarded_queue_on_reset': None if not self.drop_coverage_known else 0,
                     'wire_or_interface_loss': None},
            'model_artifact': self.model,
            'scope': 'Current IDS process loop only; excludes model training/startup/children. CPU includes logging and measurement overhead. '
                     'Stage durations overlap: detector includes nested feature/model work. RSS endpoints are not loop peak. '
                     'Observed rates are not maximum sustainable throughput or physical performance.',
        }


@contextmanager
def measured_run(enabled, output, run_id, protocol, source):
    """Write a final partial record on errors/interrupt; SIGKILL has no final.

    Only opt-in CLI runs intercept SIGTERM. The existing owner still enforces its
    own stop timeout and kill fallback; no unbounded cleanup is added here.
    """
    if not enabled:
        yield None
        return
    import json
    metrics = RuntimeMetrics(run_id, protocol, source)
    previous = signal.getsignal(signal.SIGTERM)
    def stop(_signum, _frame):
        raise MeasurementTerminated()
    signal.signal(signal.SIGTERM, stop)
    status = 'COMPLETE'
    try:
        yield metrics
    except (KeyboardInterrupt, MeasurementTerminated):
        status = 'INTERRUPTED'
        raise
    except BaseException:
        status = 'ERROR'
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
        output.write(json.dumps(metrics.report(status, final=True), allow_nan=False) + '\n')
        output.flush()
