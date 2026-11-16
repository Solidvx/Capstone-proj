"""Node A streaming IDS. Local reason codes do not alter ICD 0x200.

Thresholds are configurable engineering defaults, not measured detection guarantees.
SecOC here is an independent bus observation, never a claim about Node B's verifier.
"""
from __future__ import annotations

from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass, field
import hashlib
import hmac
import math
import struct
import uuid

from .feature_extractor import extract, FEATURE_NAMES

KNOWN_IDS = frozenset((0x100, 0x101, 0x102, 0x103, 0x200))
AUTH_ORIGINAL = {0x102: 0x100, 0x103: 0x101}


@dataclass(frozen=True)
class Observation:
    t: float  # monotonic seconds; replay uses a relative monotonic clock
    can_id: int
    data: bytes
    dlc: int = 8
    extended: bool = False
    remote: bool = False
    error: bool = False


@dataclass(frozen=True)
class Event:
    timestamp: float
    can_id: int
    reason: str
    attack_type: int = 0  # 0: unattributed diagnostic, never transmit a clearing alert
    anomaly_score: float = 1.0
    result: str = "ANOMALY"

    def alert_payload(self, epoch_seconds: int) -> bytes | None:
        if not self.attack_type:
            return None
        return struct.pack(">BBHI", self.attack_type,
                           max(0, min(255, round(self.anomaly_score * 100))),
                           self.can_id if 0 <= self.can_id <= 0x7ff else 0xffff,
                           epoch_seconds & 0xffffffff)


@dataclass(frozen=True)
class RuleEvent(Event):
    # Local evidence only. Base Event positional API and CAN bytes are unchanged.
    finding: dict | None = field(default=None,compare=False,hash=False)


@dataclass(frozen=True)
class ModelEvaluation(RuleEvent):
    """Local inference evidence only; never an attack type or a CAN alert."""
    window_start: float = 0.0
    frame_count: int = 0
    features: tuple = ()
    input_complete: bool = True


@dataclass(frozen=True)
class Config:
    missing_s: float = 0.300
    pending_s: float = 0.100
    min_period_s: float = 0.050
    max_frames_per_second: int = 100
    failure_repeat_count: int = 3
    max_soc_step: float = 20.0
    max_temperature_step: float = 20.0
    max_current_step: float = 100.0

    def __post_init__(self):
        for value in (self.missing_s, self.pending_s, self.min_period_s,
                      self.max_soc_step, self.max_temperature_step, self.max_current_step):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("IDS thresholds must be finite and positive")
        if not 1 <= self.max_frames_per_second <= 4096 or self.failure_repeat_count < 2:
            raise ValueError("invalid count thresholds")


class RuntimeDetector:
    profile = 'legacy-v1'

    def __init__(self, config: Config = Config(), key: bytes | None = None,
                 model=None, start_time: float = 0.0):
        if key is not None and len(key) != 32:
            raise ValueError("SecOC key must be exactly 32 bytes")
        if not math.isfinite(start_time):
            raise ValueError("start time must be finite")
        self.config, self.key, self.model = config, key, model
        self.known_ids = KNOWN_IDS
        self.now = self.started = start_time
        self.last_seen: dict[int, float] = {}
        self.missing: set[int] = set()
        self.pending: dict[int, Observation] = {}
        self.counters: dict[int, int] = {}
        self.last_bms: tuple[float, float, float] | None = None
        self.frames: deque[Observation] = deque(maxlen=4096)
        self.last_evicted_frame_time = None
        self.failures: deque[float] = deque(maxlen=4096)
        self.last_model_check = start_time
        self.rate_latched = False
        self.unknown_ids = deque(maxlen=4096)
        self.authenticated: dict[int, deque[bytes]] = {}
        self.finding_source_id=uuid.uuid4().hex
        self.finding_sequence=0;self.finding_epoch=0
        self.metrics = None  # Explicit measurement only; never changes a decision.

    def finding(self,reason,observed,expected,unit,*,origin='raw',authentication='not_checked'):
        """Bounded values captured at the actual decision, not inferred later.

        The ID identifies a local finding, never a CAN incident or attacker.
        No severity calibration, payload copy, MAC bytes or key is added.
        """
        if self.finding_sequence==0xffffffffffffffff:
            self.finding_source_id=uuid.uuid4().hex;self.finding_sequence=0
        self.finding_sequence+=1
        return {'schema':'ids-finding-v1','source_id':self.finding_source_id,
            'sequence':self.finding_sequence,'capture_epoch':self.finding_epoch,
            'rule_id':reason,'rule_version':'session-observation-v1' if origin=='session' else 'evidence-v3',
            'profile':self.profile,'origin':origin,'clock':'detector-monotonic-seconds',
            'observed':observed,'expected':expected,'unit':unit,'authentication':authentication,
            'model_identity_reference':'START.startup_identity.trained_model_sha256' if origin=='model' and self.profile=='session-v2' else None,
            'severity':None,'severity_policy':'not_calibrated'}

    def _event(self,now,cid,reason,attack_type=0,anomaly_score=1.0,result='ANOMALY',
               *,observed=None,expected=None,unit=None,origin='raw',authentication='not_checked'):
        return RuleEvent(now,cid,reason,attack_type,anomaly_score,result,
            self.finding(reason,observed,expected,unit,origin=origin,authentication=authentication))

    def begin_live_epoch(self, now):
        """Discard uncertain timing windows, retain authenticated anti-replay memory."""
        if not math.isfinite(now) or now < self.now:
            raise ValueError("live epoch must advance monotonic time")
        self.now=self.started=self.last_model_check=now
        self.frames.clear();self.failures.clear();self.unknown_ids.clear()
        self.last_evicted_frame_time=None
        self.pending.clear();self.last_seen.clear();self.missing.clear()
        self.last_bms=None;self.rate_latched=False
        self.finding_epoch+=1

    def _fuzzing(self, now):
        while self.unknown_ids and now-self.unknown_ids[0][0] >= 1.0:
            self.unknown_ids.popleft()
        return len({item[1] for item in self.unknown_ids}) >= 3

    def _attribute(self, now, attack_type):
        # Random IDs/payloads also hit registered IDs while fuzzing; one attack, one type.
        return 1 if self._fuzzing(now) else attack_type

    def _failure(self, now, cid, reason, attack_type=0,**finding):
        self.failures.append(now)
        while self.failures and now-self.failures[0] >= 1.0:
            self.failures.popleft()
        events = [self._event(now, cid, reason, attack_type,origin='local-secoc',**finding)]
        if len(self.failures) == self.config.failure_repeat_count:
            events.append(self._event(now,cid,'SECOC_FAILURE_BURST',observed={'failures_in_window':len(self.failures),'window_s':1.0},
                expected={'emit_at_count':self.config.failure_repeat_count},unit={'failures_in_window':'events','emit_at_count':'events','window_s':'seconds'},origin='local-secoc'))
        return events

    def tick(self, now: float) -> list[Event]:
        if not math.isfinite(now) or now < self.now:
            raise ValueError("timestamps must be finite and nondecreasing (previous="+str(self.now)+", received="+str(now)+")")
        self.now = now
        events = []
        for cid in (0x100, 0x102):
            if now-self.last_seen.get(cid, self.started) >= self.config.missing_s and cid not in self.missing:
                self.missing.add(cid)
                events.append(self._event(now,cid,'MESSAGE_MISSING',observed={
                    'last_raw_received_s':self.last_seen.get(cid),'elapsed_s':now-self.last_seen.get(cid,self.started)},
                    expected={'missing_at_s':self.config.missing_s},unit='seconds',origin='raw-timer'))
        for cid, original in list(self.pending.items()):
            if now-original.t >= self.config.pending_s:
                del self.pending[cid]
                events.extend(self._failure(now,cid,'AUTH_TIMEOUT',observed={'pending_age_s':now-original.t},
                    expected={'expiry_s':self.config.pending_s},unit='seconds'))
        while self.frames and now-self.frames[0].t >= 1.0:
            self.frames.popleft()
        if len(self.frames) < self.config.max_frames_per_second:
            self.rate_latched = False
        if self.model is not None and now-self.last_model_check >= 1.0:
            self.last_model_check = now
            if self.frames:
                with self.metrics.stage('feature_extraction') if self.metrics else nullcontext():
                    features = extract(list(self.frames))
                with self.metrics.stage('model_anomaly') if self.metrics else nullcontext():
                    score = float(self.model.anomaly(features))
                if not math.isfinite(score):
                    raise ValueError('IF returned a non-finite score')
                model_finding=self.finding('IF_WINDOW',{'anomaly':score,'features':dict(zip(FEATURE_NAMES,features))},
                    {'anomalous_when_above':0.0},{'anomaly':'model_anomaly_score','anomalous_when_above':'model_anomaly_score',
                    'features':dict(zip(FEATURE_NAMES,('frames_in_window','seconds','seconds','ids','bits','changed_bytes_per_pair','frames')))},origin='model')
                events.append(ModelEvaluation(now,0xffff,'IF_WINDOW',0,score,'MODEL_EVALUATION',finding=model_finding,
                    window_start=now-1.0,frame_count=len(self.frames),features=tuple(features),
                    input_complete=self.last_evicted_frame_time is None or now-self.last_evicted_frame_time>=1.0))
                if score > 0:
                    with self.metrics.stage('model_wire_score') if self.metrics else nullcontext():
                        wire=self.model.wire_score(features)/100
                    events.append(self._event(now,0xffff,'IF_ANOMALY',0,wire,observed={'anomaly':score,'normalized_wire_score':wire},
                        expected={'anomalous_when_above':0.0},unit={'anomaly':'model_anomaly_score','normalized_wire_score':'uint8_divided_by100'},origin='model'))
            else:
                events.append(self._event(now,0xffff,'IF_NO_INPUT',0,0.0,'MODEL_SKIPPED',observed={'frame_count':0},
                    expected={'minimum_frame_count':1},unit='frames',origin='model'))
        return events

    def observe(self, frame: Observation) -> list[Event]:
        events = self.tick(frame.t)
        cid, data = frame.can_id, frame.data
        # A single malformed frame does not prove fuzzing either.
        if frame.extended or frame.remote or frame.error or not 0 <= cid <= 0x7ff:
            return events+[self._event(frame.t,cid,'FRAME_FORMAT',self._attribute(frame.t,0),
                observed={'can_id':cid,'extended':frame.extended,'remote':frame.remote,'error':frame.error},
                expected={'can_id_min':0,'can_id_max':0x7ff,'extended':False,'remote':False,'error':False},unit='standard_frame_format')]
        if cid not in self.known_ids:
            # A single unknown ID is suspicious, but does not prove fuzzing.
            events.append(self._event(frame.t,cid,'UNKNOWN_ID',observed={'can_id':cid},expected={'allowed_ids':sorted(self.known_ids)},unit='can_id'))
            self.unknown_ids.append((frame.t, cid))
            if self._fuzzing(frame.t):
                events.append(self._event(frame.t,cid,'UNKNOWN_ID_DIVERSITY',1,
                    observed={'distinct_unknown_ids':len({item[1] for item in self.unknown_ids}),'window_s':1.0},
                    expected={'fuzz_at_distinct_ids':3},unit={'distinct_unknown_ids':'ids','fuzz_at_distinct_ids':'ids','window_s':'seconds'}))
        if frame.dlc != 8 or len(data) != 8:
            return events+[self._event(frame.t,cid,'DLC',self._attribute(frame.t,0),observed={'dlc':frame.dlc,'data_bytes':len(data)},expected={'dlc':8,'data_bytes':8},unit='bytes')]
        # Do not learn/trigger on the IDS's own alert stream.
        if cid == 0x200:
            return events
        if len(self.frames)==self.frames.maxlen:
            if self.metrics:self.metrics.counts['feature_buffer_evictions'] += 1
            self.last_evicted_frame_time=self.frames[0].t
        self.frames.append(frame)
        if len(self.frames) >= self.config.max_frames_per_second and not self.rate_latched:
            self.rate_latched = True
            counts: dict[int, int] = {}
            for item in self.frames:
                counts[item.can_id] = counts.get(item.can_id, 0)+1
            top = max(counts, key=counts.get)
            # Flooding: one unregistered ID owns the window. A fast registered or
            # diverse stream is replay/spoofing/fuzzing evidence, not flooding.
            flood = top not in self.known_ids and counts[top]*2 > len(self.frames)
            events.append(self._event(frame.t,top if flood else cid,'FRAME_RATE',4 if flood else 0,
                observed={'frame_count':len(self.frames),'dominant_id':top,'dominant_count':counts[top],'dominant_known':top in self.known_ids},
                expected={'rate_at_count':self.config.max_frames_per_second,'window_s':1.0,'dominant_for_flood':'unknown_id_and_strictly_more_than_half'},
                unit={'frame_count':'frames_in_window','rate_at_count':'frames_in_window','dominant_id':'can_id','dominant_count':'frames','window_s':'seconds'}))
        if cid not in self.known_ids:
            return events
        previous = self.last_seen.get(cid)
        self.last_seen[cid] = frame.t
        self.missing.discard(cid)
        if cid in (0x100, 0x102) and previous is not None and frame.t-previous < self.config.min_period_s:
            events.append(self._event(frame.t,cid,'PERIOD_TOO_SHORT',observed={'raw_interval_s':frame.t-previous},
                expected={'minimum_s':self.config.min_period_s},unit='seconds'))
        if cid == 0x100:
            if data[0] > 200 or data[1] > 200 or data[6] > 165 or data[7] != 0:
                return events+[self._event(frame.t,cid,'BMS_RANGE',self._attribute(frame.t,3),
                    observed={'soc_percent':data[0]*.5,'soh_percent':data[1]*.5,'temperature_c':data[6]-40,'reserved':data[7]},
                    expected={'soc_percent_max':100,'soh_percent_max':100,'temperature_c_max':125,'reserved':0},
                    unit={'soc_percent':'percent','soh_percent':'percent','temperature_c':'celsius','reserved':'byte'})]
            values = (data[0]*0.5, data[6]-40, int.from_bytes(data[4:6],"big",signed=True)*0.1)
            if self.last_bms is not None:
                limits=(self.config.max_soc_step,self.config.max_temperature_step,self.config.max_current_step)
                if any(abs(a-b)>limit for a,b,limit in zip(values,self.last_bms,limits)):
                    events.append(self._event(frame.t,cid,'BMS_STEP',self._attribute(frame.t,3),
                        observed={'previous_raw_values':self.last_bms,'current_raw_values':values,'absolute_delta':[abs(a-b) for a,b in zip(values,self.last_bms)]},
                        expected={'maximum_delta':limits},unit={'previous_raw_values':['percent','celsius','ampere'],
                        'current_raw_values':['percent','celsius','ampere'],'absolute_delta':['percentage_points','celsius','ampere'],
                        'maximum_delta':['percentage_points','celsius','ampere']}))
            self.last_bms=values  # raw observation, not authenticated application state
        if cid == 0x101 and (data[0]>3 or data[1]>3 or not 1<=data[2]<=7 or data[3]>200 or data[4]>165 or any(data[5:])):
            return events+[self._event(frame.t,cid,'FAILSAFE_RANGE',self._attribute(frame.t,3),
                observed={'previous_state':data[0],'state':data[1],'reason':data[2],'soc_percent':data[3]*.5,'temperature_c':data[4]-40,'nonzero_reserved_bytes':sum(value!=0 for value in data[5:]),'transition_semantics_checked':False},
                expected={'state_max':3,'reason_min':1,'reason_max':7,'soc_percent_max':100,'temperature_c_max':125,'nonzero_reserved_bytes':0},
                unit={'previous_state':'enum','state':'enum','reason':'code','soc_percent':'percent','temperature_c':'celsius','nonzero_reserved_bytes':'bytes'})]
        if self.key is None:
            return events
        if cid in (0x100,0x101):
            if cid in self.pending:
                events.append(self._event(frame.t,cid,'PENDING_REPLACED',result='DIAGNOSTIC',
                    observed={'previous_pending_age_s':frame.t-self.pending[cid].t},expected={'pending_slots_per_id':1},
                    unit={'previous_pending_age_s':'seconds','pending_slots_per_id':'slots'},origin='local-secoc'))
            self.pending[cid]=frame
        elif cid in AUTH_ORIGINAL:
            original_id=AUTH_ORIGINAL[cid]
            original=self.pending.get(original_id)
            if original is None:
                return events+self._failure(frame.t,original_id,'AUTH_ORPHAN',observed={'pending_original':False},expected={'pending_original':True},unit='presence')
            counter=int.from_bytes(data[4:],"big")
            last=self.counters.get(original_id)
            if last is not None:
                delta=(counter-last)&0xffffffff
                if not 1<=delta<=100:
                    reason="COUNTER_REUSE" if delta==0 else "COUNTER_BACKWARD" if delta>0x80000000 else "COUNTER_WINDOW"
                    # Only a reused/old counter is a replay signature; a forward jump is not.
                    return events+self._failure(frame.t,original_id,reason,
                                                self._attribute(frame.t,0 if reason=="COUNTER_WINDOW" else 2),
                                                observed={'counter':counter,'last_authenticated_counter':last,'delta_u32':delta},
                                                expected={'forward_delta_min':1,'forward_delta_max':100},unit='uint32_counter')
            expected=hmac.new(self.key,struct.pack(">HI",original_id,counter)+original.data,hashlib.sha256).digest()[:4]
            if not hmac.compare_digest(expected,data[:4]):
                # A previously authenticated original under a fresh counter was replayed, not forged.
                replayed=original.data in self.authenticated.get(original_id,())
                return events+self._failure(frame.t,original_id,'MAC_FAIL',self._attribute(frame.t,2 if replayed else 3),
                    observed={'tag_matches':False,'original_previously_authenticated':replayed},expected={'tag_matches':True},unit='boolean',authentication='failed')
            self.counters[original_id]=counter
            self.authenticated.setdefault(original_id,deque(maxlen=256)).append(original.data)
            del self.pending[original_id]
        return events
