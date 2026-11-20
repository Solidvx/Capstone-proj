"""Session-v2 local IDS evidence; independent from the IVI application verifier.

The current key context comes only from the inherited ECU-owned pipe. Bounded
raw/auth candidates tolerate either receive order. Inconclusive expiry is not a
claim about IVI rejection or a completed attack block.
"""
from collections import OrderedDict, deque
from dataclasses import dataclass
import struct
from security.can_session import context_id
from security.can_session import data_mac, tag_matches
from .runtime_detector import RuntimeDetector, RuleEvent

SESSION_IDS=frozenset((0x100,0x101,0x102,0x103,0x104,0x105,0x200,0x300,0x301,0x302,0x303))
PAIRS={0x102:0x100,0x103:0x101,0x105:0x104}


@dataclass(frozen=True)
class EvidenceEvent(RuleEvent):
    reference_hex: str = ''
    evidence_bits: int = 0
    candidate_index: int = 0


class SessionDetector(RuntimeDetector):
    profile = 'session-v2'

    def __init__(self, config, source, model=None, start_time=0.0, *, max_checks=128):
        if type(max_checks) is not int or not 1<=max_checks<=4096:raise ValueError('invalid MAC budget')
        super().__init__(config,None,model,start_time)
        self.known_ids=SESSION_IDS;self.source=source;self.max_checks=max_checks
        self.raw={cid:deque(maxlen=4) for cid in PAIRS.values()}
        self.auth={cid:deque(maxlen=4) for cid in PAIRS.values()}
        self.seen=OrderedDict();self.highest=None;self.last_authenticated=None
        self.check_start=start_time;self.checks=0;self.budget_exhausted=False
        self.context_now=start_time;self.authenticated_pairs=deque(maxlen=256)
        self.last_flood_update=float("-inf")
        self.candidate_index=0

    def replay_evidence(self,now,cid,raw,auth):
        self.candidate_index+=1
        auth_id=0x105 if cid==0x104 else cid+2
        reference=bytes((2,8,8,0))+struct.pack('>II',cid,auth_id)+context_id(self.source.context)+raw.data+auth.data
        return EvidenceEvent(now,cid,'SESSION_COUNTER_REPLAY',self._attribute(now,2 if cid!=0x104 else 0),
            finding=self.finding('SESSION_COUNTER_REPLAY',
                {'counter':int.from_bytes(auth.data[4:],'big'),'highest_authenticated_counter':self.highest,
                 'counter_seen':int.from_bytes(auth.data[4:],'big') in self.seen},
                {'unique_global_counter':True,'maximum_reorder_distance':100},'uint32_counter',origin='session',authentication='verified'),
            reference_hex=reference.hex(),evidence_bits=4,candidate_index=self.candidate_index)

    def begin_live_epoch(self, now):
        super().begin_live_epoch(now)
        for queue in (*self.raw.values(),*self.auth.values()):queue.clear()
        self.last_authenticated=None;self.check_start=now;self.checks=0
        self.budget_exhausted=False;self.context_now=now

    def update_context(self, now):
        self.context_now=now
        generation=self.source.generation
        if self.source.poll(now):
            for queue in (*self.raw.values(),*self.auth.values()):queue.clear()
            if generation!=self.source.generation:self.seen.clear();self.highest=None
            self.last_authenticated=None;self.last_bms=None

    def unavailable_reason(self, now):
        if not self.source.ready(max(now,self.context_now)):return 4
        if self.budget_exhausted:return 5
        if self.last_authenticated is None or not 0<=now-self.last_authenticated<self.config.missing_s:return 2
        return 0

    def observation_ready(self, now):
        return (self.source.ready(max(now,self.context_now)) and not self.budget_exhausted and self.last_authenticated is not None
                and 0<=now-self.last_authenticated<self.config.missing_s)

    def tick(self, now):
        events=super().tick(now)
        if now-self.check_start>=1:
            self.check_start=now;self.checks=0;self.budget_exhausted=False
        if self.rate_latched and len(self.frames)>=self.config.max_frames_per_second and now-self.last_flood_update>=.25:
            counts={}
            for frame in self.frames:counts[frame.can_id]=counts.get(frame.can_id,0)+1
            dominant=max(counts,key=counts.get)
            if dominant not in self.known_ids and counts[dominant]*2>len(self.frames) and not self._fuzzing(now):
                events.append(self._event(now,dominant,'FRAME_RATE_ONGOING',4,
                    observed={'frame_count':len(self.frames),'dominant_id':dominant,'dominant_count':counts[dominant],'dominant_known':False,'fuzzing':False},
                    expected={'rate_at_count':self.config.max_frames_per_second,'window_s':1.0,'minimum_update_s':.25,'dominant_for_flood':'unknown_id_and_strictly_more_than_half'},
                    unit={'frame_count':'frames_in_window','rate_at_count':'frames_in_window','dominant_id':'can_id','dominant_count':'frames','window_s':'seconds','minimum_update_s':'seconds'},origin='session'));self.last_flood_update=now
        for cid,raws in self.raw.items():
            auths=self.auth[cid]
            # Only an unambiguous isolated expired pair permits a MAC-failure
            # attribution. Overlapping unmatched candidates remain diagnostic.
            if len(raws)==len(auths)==1 and now-max(raws[0].t,auths[0].t)>=self.config.pending_s:
                ready=None if self.budget_exhausted else self.source.ready(max(now,self.context_now))
                if not self.budget_exhausted and ready:
                    replay=(cid,raws[0].data,auths[0].data) in self.authenticated_pairs
                    events.append(self._event(now,cid,'SESSION_MAC_FAIL',self._attribute(now,2 if replay else 3),
                        observed={'tag_matches':False,'original_previously_authenticated':replay,'candidate_count_each_side':1},
                        expected={'tag_matches':True},unit={'tag_matches':'boolean','original_previously_authenticated':'boolean','candidate_count_each_side':'frames'},origin='session',authentication='failed'))
                else:events.append(self._event(now,cid,'SESSION_PAIR_UNCERTAIN',
                    observed={'context_ready':ready,'mac_budget_exhausted':self.budget_exhausted},
                    expected={'context_ready':True,'mac_budget_exhausted':False},unit='boolean',origin='session'))
                raws.clear();auths.clear()
            for side,queue in (('original',raws),('authentication',auths)):
                while queue and now-queue[0].t>=self.config.pending_s:
                    expired=queue.popleft();events.append(self._event(now,cid,'SESSION_PAIR_EXPIRED',
                        observed={'candidate_side':side,'candidate_age_s':now-expired.t},expected={'expiry_s':self.config.pending_s},unit='seconds',origin='session'))
        return events

    def observe(self, frame):
        events=super().observe(frame)
        cid=PAIRS.get(frame.can_id,frame.can_id)
        if cid not in self.raw or frame.can_id not in (*PAIRS.keys(),*PAIRS.values()):return events
        if frame.extended or frame.remote or frame.error or frame.dlc!=8 or len(frame.data)!=8:return events
        if not self.source.ready(max(frame.t,self.context_now)) or round(frame.t*1e9)<self.source.boundary_ns:return events
        queue=self.auth[cid] if frame.can_id in PAIRS else self.raw[cid]
        if len(queue)==queue.maxlen:
            events.append(self._event(frame.t,cid,'SESSION_CANDIDATE_LIMIT',
                observed={'candidate_count_before_append':len(queue),'side':'authentication' if frame.can_id in PAIRS else 'original'},
                expected={'capacity':queue.maxlen},unit='frames',origin='session'));self.budget_exhausted=True
        queue.append(frame)
        for raw in list(self.raw[cid]):
            for auth in list(self.auth[cid]):
                if self.checks>=self.max_checks:
                    self.budget_exhausted=True
                    return events+[self._event(frame.t,cid,'SESSION_MAC_BUDGET',observed={'checks_in_window':self.checks},
                        expected={'maximum_checks':self.max_checks,'window_s':1.0},unit={'checks_in_window':'MAC_comparisons','maximum_checks':'MAC_comparisons','window_s':'seconds'},origin='session')]
                self.checks+=1
                counter=int.from_bytes(auth.data[4:],'big')
                if not tag_matches(data_mac(self.source.keys['data'],cid,counter,raw.data),auth.data[:4]):continue
                self.raw[cid].remove(raw);self.auth[cid].remove(auth)
                previous=self.seen.get(counter)
                if previous is not None:
                    reason='SESSION_COUNTER_REPLAY' if previous==(cid,raw.data) else 'SESSION_AUTHENTICATED_CONFLICT'
                    attack=2 if reason=='SESSION_COUNTER_REPLAY' and cid!=0x104 else 0
                    events.append(self.replay_evidence(frame.t,cid,raw,auth) if attack==2 else self._event(frame.t,cid,reason,self._attribute(frame.t,attack),
                        observed={'counter':counter,'same_authenticated_payload':previous==(cid,raw.data)},
                        expected={'unique_global_counter':True,'same_payload_for_duplicate':True},unit='uint32_counter',origin='session',authentication='verified'))
                    return events
                if self.highest is not None and counter+100<self.highest:
                    return events+[self.replay_evidence(frame.t,cid,raw,auth)]
                if self.highest is not None and counter>self.highest+100:
                    return events+[self._event(frame.t,cid,'SESSION_COUNTER_WINDOW',
                        observed={'counter':counter,'highest_authenticated_counter':self.highest,'forward_delta':counter-self.highest},
                        expected={'maximum_forward_delta':100},unit='uint32_counter',origin='session',authentication='verified')]
                self.highest=max(counter,self.highest if self.highest is not None else counter)
                self.seen[counter]=(cid,raw.data)
                self.authenticated_pairs.append((cid,raw.data,auth.data))
                if len(self.seen)>256:self.seen.popitem(last=False)
                if cid==0x100:self.last_authenticated=frame.t
                return events
        return events
