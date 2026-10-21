import hashlib
import hmac
import io
import struct
import unittest

from security.ids.runtime_detector import Config, Event, Observation, RuntimeDetector
from security.ids.runtime import AlertThrottle, run_replay

KEY=bytes(32)  # Explicit dummy test key.
BMS=bytes([150,190,0x10,0x68,0xff,0xec,65,0])

def auth(counter,payload=BMS,cid=0x100):
    return hmac.new(KEY,struct.pack(">HI",cid,counter)+payload,hashlib.sha256).digest()[:4]+counter.to_bytes(4,"big")

def frame(t,cid=0x100,data=BMS):
    return Observation(t,cid,data)


class RuntimeIdsTests(unittest.TestCase):
    def test_normal_signed_stream(self):
        d=RuntimeDetector(key=KEY)
        for i in range(100):
            self.assertEqual(d.observe(frame(i*0.1)),[])
            self.assertEqual(d.observe(frame(i*0.1+0.001,0x102,auth(i))),[])
        self.assertEqual(d.counters,{0x100:99})

    def test_formats_ranges_and_jumps(self):
        d=RuntimeDetector()
        self.assertIn("UNKNOWN_ID",[e.reason for e in d.observe(frame(0,0x555))])
        self.assertIn("DLC",[e.reason for e in d.observe(Observation(0,0x100,b"",0))])
        self.assertIn("FRAME_FORMAT",[e.reason for e in d.observe(Observation(0,0x100,BMS,8,True))])
        self.assertIn("BMS_RANGE",[e.reason for e in d.observe(frame(0,data=bytes([201])+BMS[1:]))])
        d.observe(frame(0.1))
        self.assertIn("BMS_STEP",[e.reason for e in d.observe(frame(0.2,data=bytes([30])+BMS[1:]))])
        self.assertIn("FAILSAFE_RANGE",[e.reason for e in d.observe(frame(0.2,0x101,bytes(8)))])

    def test_timer_without_frames_and_recovery(self):
        d=RuntimeDetector(key=KEY)
        d.observe(frame(0))
        self.assertEqual(d.tick(0.099),[])
        self.assertIn("AUTH_TIMEOUT",[e.reason for e in d.tick(0.1)])
        self.assertEqual(d.tick(0.2),[])
        self.assertEqual(len([e for e in d.tick(0.3) if e.reason=="MESSAGE_MISSING"]),2)
        self.assertEqual(d.tick(0.4),[])
        d.observe(frame(0.5))
        self.assertIn("MESSAGE_MISSING",[e.reason for e in d.tick(0.81)])
        self.assertNotIn(0x101,d.missing) # event-driven messages have no periodic timeout

    def test_mac_counter_window_wrap_and_independent_pairs(self):
        d=RuntimeDetector(key=KEY)
        d.observe(frame(0));d.observe(frame(.001,0x102,auth(0xffffffff)))
        d.observe(frame(.1));self.assertEqual(d.observe(frame(.101,0x102,auth(0))),[])
        for i,(counter,reason) in enumerate([(0,"COUNTER_REUSE"),(0xffffffff,"COUNTER_BACKWARD"),(101,"COUNTER_WINDOW")]):
            now=.2+i*.1;d.observe(frame(now))
            self.assertIn(reason,[e.reason for e in d.observe(frame(now+.001,0x102,auth(counter)))])
        self.assertEqual(d.counters[0x100],0)
        d.observe(frame(.5));bad=bytearray(auth(100));bad[0]^=1
        self.assertIn("MAC_FAIL",[e.reason for e in d.observe(frame(.501,0x102,bytes(bad)))])
        self.assertEqual(d.counters[0x100],0)
        d.observe(frame(.6));d.observe(frame(.601,0x102,auth(100)))
        self.assertEqual(d.counters[0x100],100)
        fs=bytes([0,1,1,30,65,0,0,0]);d.observe(frame(.602,0x101,fs))
        d.observe(frame(.603,0x103,auth(7,fs,0x101)))
        self.assertEqual(d.counters[0x101],7)

    def test_repeat_rate_and_bounded_storage(self):
        d=RuntimeDetector(Config(max_frames_per_second=10),KEY)
        d.observe(frame(0));bad=bytes(8)
        events=[]
        for i in range(3):events+=d.observe(frame(.001+i*.001,0x102,bad))
        self.assertIn("SECOC_FAILURE_BURST",[e.reason for e in events])
        events=[]
        for i in range(5000):events+=d.observe(frame(.05,0x555))
        self.assertEqual(len(d.frames),4096)
        self.assertEqual(sum(e.reason=="FRAME_RATE" for e in events),1)
        self.assertLessEqual(len(d.last_seen),5)

    def test_no_alert_loop_or_unattributed_clear(self):
        d=RuntimeDetector()
        for _ in range(100):self.assertEqual(d.observe(frame(0,0x200)),[])
        self.assertEqual(len(d.frames),0)
        self.assertIsNone(Event(0,0x100,"MESSAGE_MISSING").alert_payload(1))
        wire=Event(0,0x100,"COUNTER_REUSE",2,1.5).alert_payload(0x100000001)
        self.assertEqual(wire,bytes.fromhex("0296010000000001"))

    def test_if_and_replay_output(self):
        class Model:
            def anomaly(self,v):self.vector=v;return 1.0
            def wire_score(self,v):return 200
        model=Model();d=RuntimeDetector(model=model)
        output=io.StringIO()
        count=run_replay(d,[frame(.9),1.0],output)
        self.assertGreater(count,0)
        self.assertIn('"reason": "IF_ANOMALY"',output.getvalue())
        self.assertEqual(len(model.vector),7)

    def test_config_and_time_rejection(self):
        with self.assertRaises(ValueError):Config(missing_s=-1)
        with self.assertRaises(ValueError):RuntimeDetector(key=b"short")
        d=RuntimeDetector();d.tick(1)
        with self.assertRaises(ValueError):d.tick(.5)
        with self.assertRaises(ValueError):d.tick(float('nan'))

    def test_alert_throttle_preserves_later_flooding_classification(self):
        throttle=AlertThrottle(.1)
        fuzzy=Event(.0,0,"UNKNOWN_ID",1)
        flooding=Event(.03,0,"FRAME_RATE",4)
        throttle.offer(fuzzy)
        self.assertEqual(throttle.pop_ready(.0),fuzzy)
        throttle.offer(flooding)
        self.assertIsNone(throttle.pop_ready(.03))
        self.assertEqual(throttle.pop_ready(.1),flooding)
        throttle.offer(Event(.2,0,"UNKNOWN_ID",1))
        self.assertEqual(throttle.pop_ready(.2).attack_type,1)

    def test_mixed_attacks_are_fair_under_continuous_flooding(self):
        throttle=AlertThrottle(.1)
        throttle.offer(Event(0,0,"FRAME_RATE",4))
        throttle.pop_ready(0)
        for kind in (3,2,1,4):
            throttle.offer(Event(.01,0,"attack",kind))
        sent=[]
        for now in (.11,.22,.33,.44):
            throttle.offer(Event(now,0,"FRAME_RATE",4))
            sent.append(throttle.pop_ready(now).attack_type)
        self.assertEqual(sent,[3,2,1,4])

if __name__=="__main__":unittest.main()
