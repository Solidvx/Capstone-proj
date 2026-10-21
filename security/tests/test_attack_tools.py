import argparse
import hashlib
import hmac
import random
import socket
import struct
import unittest
from unittest.mock import Mock, patch

from security.attack_simulator import (
    SPOOFED_BMS,
    build_attack_frame,
    parse_payload,
    validate_safety,
)
from security.can_socket import SocketCanTransport
from security.secoc_tamper_fixture import BASELINE, RECOVERY, TAMPERED, build_sequence


class AttackSimulatorTests(unittest.TestCase):
    def test_four_attack_payloads_are_deterministic_and_well_formed(self):
        fuzzy_a = build_attack_frame("fuzzy", random.Random(42))
        fuzzy_b = build_attack_frame("fuzzy", random.Random(42))
        self.assertEqual(fuzzy_a, fuzzy_b)
        self.assertTrue(0 <= fuzzy_a[0] <= 0x7FF)
        self.assertEqual(len(fuzzy_a[1]), 8)
        self.assertEqual(build_attack_frame("replay", random.Random(1), bytes(range(8))),
                         (0x100, bytes(range(8))))
        self.assertEqual(build_attack_frame("spoofing", random.Random(1)),
                         (0x100, SPOOFED_BMS))
        self.assertEqual(build_attack_frame("flooding", random.Random(1)),
                         (0x000, bytes(8)))

    def test_physical_interface_requires_explicit_bounded_confirmation(self):
        validate_safety("vcan0", 60, 4000, False)
        with self.assertRaises(ValueError):
            validate_safety("can0", 1, 10, False)
        with self.assertRaises(ValueError):
            validate_safety("can0", 11, 10, True)
        with self.assertRaises(ValueError):
            validate_safety("can0", 1, 4001, True)
        validate_safety("can0", 10, 4000, True)

    def test_replay_payload_validation(self):
        self.assertEqual(parse_payload("0011223344556677"), bytes.fromhex("0011223344556677"))
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_payload("00")

    def test_shared_socketcan_codec_and_cleanup(self):
        fake = Mock()
        fake.recv.return_value = struct.pack("=IB3x8s", 0x100, 8, bytes(range(8)))
        fake.send.return_value = 16
        with patch("security.can_socket.socket.socket", return_value=fake), \
             patch("security.can_socket.socket.AF_CAN", 29, create=True), \
             patch("security.can_socket.socket.CAN_RAW", 1, create=True):
            with SocketCanTransport("test-only") as transport:
                frame = transport.receive()
                self.assertEqual(frame.can_id, 0x100)
                self.assertEqual(frame.data, bytes(range(8)))
                transport.send(0x200, b"\x01")
                self.assertEqual(fake.send.call_args.args[0],
                                 struct.pack("=IB3x8s", 0x200, 1, b"\x01" + bytes(7)))
                fake.recv.side_effect = socket.timeout()
                self.assertIsNone(transport.receive())
            fake.close.assert_called_once()


class TamperFixtureTests(unittest.TestCase):
    def test_bad_mac_does_not_consume_counter_and_recovery_is_valid(self):
        key = bytes(range(32))
        sequence = build_sequence(key, 7)
        self.assertEqual([item[0] for item in sequence], [0x100, 0x102] * 3)
        self.assertEqual(sequence[0][1], BASELINE)
        self.assertEqual(sequence[2][1], TAMPERED)
        self.assertEqual(sequence[4][1], RECOVERY)

        def expected(counter, payload):
            message = struct.pack(">HI8s", 0x100, counter, payload)
            return hmac.new(key, message, hashlib.sha256).digest()[:4]

        self.assertEqual(sequence[1][1][:4], expected(7, BASELINE))
        self.assertNotEqual(sequence[3][1][:4], expected(8, TAMPERED))
        self.assertEqual(sequence[3][1][4:], struct.pack(">I", 8))
        self.assertEqual(sequence[5][1][:4], expected(8, RECOVERY))
        self.assertEqual(sequence[5][1][4:], struct.pack(">I", 8))

    def test_key_and_counter_validation(self):
        with self.assertRaises(ValueError):
            build_sequence(b"short", 0)
        with self.assertRaises(ValueError):
            build_sequence(bytes(32), -1)


if __name__ == "__main__":
    unittest.main()
