"""ECU-owned, receive-only private pipe for authenticated IVI rejection reports.

Receipt/verification times are ECU-local. No IVI source-event age, attacker
identity, new attack label or IF feature is inferred from these diagnostics.
"""
from collections import Counter,deque
import fcntl
import os
import select
import stat
import struct

from security.can_diagnostic import valid_body

PACKET=struct.Struct('>4sQQQQI16sQ80s')


class PeerDiagnostics:
    def __init__(self,fd,context):
        info=os.fstat(fd);flags=fcntl.fcntl(fd,fcntl.F_GETFL)
        if fd<3 or not stat.S_ISFIFO(info.st_mode) or not flags&os.O_NONBLOCK or flags&os.O_ACCMODE!=os.O_RDONLY:
            raise ValueError('peer diagnostics require inherited nonblocking read pipe')
        self.fd=fd;self.context=context;self.buffer=b'';self.failed=False
        self.generation=None;self.highest_sequence=None;self.sequences=set();self.last_published=0;self.last_drop=0;self.last_now=0
        self.ids=deque();self.seen={};self.recent=deque(maxlen=256)
        self.truncated_until=0

    def close(self):
        fd,self.fd=self.fd,-1
        if fd>=0:
            try:os.close(fd)
            except OSError:pass # Failed channel is never reused/retried; raw IDS must continue.

    def poll(self,now_ns):
        if self.failed:return []
        records=[];processing_bytes=0
        try:
            if type(now_ns) is not int or now_ns<self.last_now:raise ValueError('local clock regressed')
            self.last_now=now_ns
            if hasattr(select,'poll'):
                probe=select.poll();probe.register(self.fd,select.POLLHUP|select.POLLERR)
                if probe.poll(0):raise ValueError('ECU peer pipe closed')
            try:data=os.read(self.fd,PACKET.size*8-len(self.buffer))
            except BlockingIOError:data=None
            if data==b'':raise ValueError('ECU peer pipe EOF')
            if data:self.buffer+=data
            while len(self.buffer)>=PACKET.size:
                packet=self.buffer[:PACKET.size];self.buffer=self.buffer[PACKET.size:]
                processing_bytes=PACKET.size
                records.append(self.consume(packet,now_ns))
                processing_bytes=0
            return records
        except (OSError,ValueError) as error:
            self.failed=True;pending=len(self.buffer)+processing_bytes;self.buffer=b'';self.close()
            return records+[{'result':'PEER_DIAGNOSTIC_UNAVAILABLE','timestamp':now_ns/1e9,'reason':str(error),
                     'unconfirmed_buffer_bytes':pending,'raw_if_continues':True}]

    def consume(self,packet,now_ns):
        magic,generation,published,received,verified,sequence,session,drops,body=PACKET.unpack(packet)
        if magic!=b'CPR1' or not generation or not 0<received<=verified<=published<=now_ns or not valid_body(0x303,5,body):
            raise ValueError('invalid peer rejection packet')
        base={'timestamp':now_ns/1e9,'envelope_sequence':sequence,'session_id':session.hex(),
              'ecu_generation':generation,'rejection_id':body[16:32].hex()}
        context=self.context
        if (not context.ready(now_ns/1e9) or generation!=context.generation or session.hex()!=context.fingerprint()
                or published<context.boundary_ns):
            return dict(base,result='PEER_DIAGNOSTIC_IGNORED',reason='CONTEXT_UNCONFIRMED')
        if self.generation!=generation:
            self.generation=generation;self.highest_sequence=None;self.sequences.clear();self.last_published=0
            self.ids.clear();self.seen.clear();self.recent.clear()
            self.truncated_until=0
        if drops<self.last_drop:raise ValueError('peer drop counter regressed')
        # Preserve explicit producer drops; sequence gaps may be other kinds.
        lost=drops-self.last_drop;self.last_drop=drops
        if lost:self.truncated_until=max(self.truncated_until,now_ns+1_000_000_000)
        # CAN diagnostics permit unseen reverse-order messages in a64-slot
        # window. Do not turn a valid late report into a duplicate here.
        if sequence in self.sequences or (self.highest_sequence is not None and sequence+64<=self.highest_sequence):
            return dict(base,result='PEER_DIAGNOSTIC_IGNORED',reason='OLD_OR_DUPLICATE_SEQUENCE',producer_drops=lost)
        if published<self.last_published:raise ValueError('peer publication clock regressed')
        self.highest_sequence=max(sequence,self.highest_sequence if self.highest_sequence is not None else sequence)
        self.sequences.add(sequence);self.sequences={seq for seq in self.sequences if seq+64>self.highest_sequence}
        self.last_published=published
        if now_ns-verified>=3_000_000_000:
            return dict(base,result='PEER_DIAGNOSTIC_IGNORED',reason='STALE_LOCAL_DELIVERY',producer_drops=lost)
        identity=(body[:16],body[16:32])
        if identity in self.seen:
            if self.seen[identity]!=body:
                self.truncated_until=max(self.truncated_until,now_ns+1_000_000_000)
                return dict(base,result='PEER_DIAGNOSTIC_IGNORED',reason='CONFLICTING_REJECTION_ID',
                    producer_drops=lost,body_hex=body.hex(),previous_body_hex=self.seen[identity].hex(),
                    recent_1s_count_complete=False)
            return dict(base,result='PEER_DIAGNOSTIC_IGNORED',reason='DUPLICATE_REJECTION_ID',producer_drops=lost)
        if len(self.ids)==256:self.seen.pop(self.ids.popleft())
        self.ids.append(identity);self.seen[identity]=body
        while self.recent and now_ns-self.recent[0][0]>=1_000_000_000:self.recent.popleft()
        if now_ns-published<1_000_000_000:
            if len(self.recent)==256:self.truncated_until=max(self.truncated_until,self.recent[0][0]+1_000_000_000)
            self.recent.append((published,body[32]))
        return dict(base,result='PEER_REJECTION_CONSUMED',peer_instance=body[:16].hex(),
            ecu_received_ns=received,ecu_verified_ns=verified,ecu_forwarded_ns=published,ids_consumed_ns=now_ns,
            producer_drops=lost,producer_drops_total=drops,reason=body[32],mac_verified=bool(body[33]),
            treatment=body[34],body_hex=body.hex(),recent_1s_reason_counts=dict(Counter(reason for _,reason in self.recent)),
            recent_1s_count_complete=now_ns>=self.truncated_until,
            diagnostic_only=True,attack_type_inferred=False,if_features_changed=False,source_event_age_known=False)
