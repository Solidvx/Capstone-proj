"""Public session transcript from an inherited ECU-owned local pipe.

No keys are transported. CAN observations cannot select the active context.
The process owner must establish the pipe; credentials are inherited ownership.
"""
import fcntl
import math
import os
import stat
import select
import struct
from security.can_session import SessionContext, derive_keys, context_id

PACKET = struct.Struct('>4sB3xQQQH16s16s')


class ContextSource:
    def __init__(self, fd, shared_key, *, timeout_s=3.0, clock=None):
        if len(shared_key)!=32 or not math.isfinite(timeout_s) or timeout_s<=0:
            raise ValueError('context requires key and finite timeout')
        info=os.fstat(fd);flags=fcntl.fcntl(fd,fcntl.F_GETFL)
        if fd<3 or not stat.S_ISFIFO(info.st_mode) or not flags&os.O_NONBLOCK or flags&os.O_ACCMODE!=os.O_RDONLY:
            raise ValueError('inherited nonblocking read pipe required')
        self.fd=fd;self.shared_key=shared_key;self.timeout_s=timeout_s;self.clock=clock
        self.buffer=b'';self.generation=0;self.boundary_ns=0;self.received_at=None
        self.context=None;self.keys=None;self.open=False;self.eof=False

    def poll(self, now):
        changed=False
        try:data=os.read(self.fd,PACKET.size*8)
        except BlockingIOError:data=None
        if self.clock is not None:now=self.clock()
        if hasattr(select,"poll"):
            probe=select.poll();probe.register(self.fd,select.POLLHUP|select.POLLERR)
            if any(flags&(select.POLLHUP|select.POLLERR) for _,flags in probe.poll(0)):
                self.eof=True;self.open=False
        if data==b'':self.eof=True;self.open=False
        if data:self.buffer+=data
        while len(self.buffer)>=PACKET.size:
            packet=self.buffer[:PACKET.size];self.buffer=self.buffer[PACKET.size:]
            magic,opened,generation,boundary,published,tid,nonce_b,nonce_a=PACKET.unpack(packet)
            if magic!=b'CSC1' or packet[5:8]!=bytes(3) or opened not in (0,1) or not boundary<=published<=round(now*1e9):
                raise ValueError('invalid ECU context packet')
            if generation<self.generation or boundary<self.boundary_ns:
                raise ValueError('ECU context moved backward')
            if generation==0 and (tid or nonce_b!=bytes(16) or nonce_a!=bytes(16)):
                raise ValueError("closed initial context must be empty")
            if opened and generation==0:raise ValueError('open context without generation')
            context=SessionContext(tid,nonce_b,nonce_a) if generation else None
            if generation==self.generation and self.context is not None and context!=self.context:
                raise ValueError('context changed without generation')
            if generation!=self.generation:
                self.keys=derive_keys(self.shared_key,context) if context else None
                changed=True
            changed|=self.open!=bool(opened)
            self.context=context;self.generation=generation;self.boundary_ns=boundary
            self.open=bool(opened) and not self.eof;self.received_at=published/1e9
        return changed

    def ready(self, now):
        if self.clock is not None:now=self.clock()
        return (not self.eof and self.open and self.keys is not None and self.received_at is not None
                and 0<=now-self.received_at<self.timeout_s)

    def fingerprint(self):
        return context_id(self.context).hex() if self.context is not None else None
