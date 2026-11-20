"""Explicit public dummy inputs for independent diagnostic cross vectors."""
from security.can_session import SessionContext, context_id, data_mac, derive_keys
from security.can_diagnostic import encode


def uuid_bytes(value):
    data = bytearray([value] * 16)
    data[6] = 0x40 | (value & 15)
    data[8] = 0x80 | (value & 63)
    return bytes(data)


def put(body, at, value, size=4):
    body[at:at+size] = value.to_bytes(size, "big")


def fixtures():
    ctx = SessionContext(0x1234, b"B" * 16, b"A" * 16)
    keys = derive_keys(bytes(range(32)), ctx)
    reference = bytearray(44)
    reference[:4] = bytes((2, 8, 8, 0))
    put(reference, 4, 0x100)
    put(reference, 8, 0x102)
    reference[12:28] = context_id(ctx)
    raw = bytes.fromhex("96c81068ffec4100")
    reference[28:36] = raw
    reference[36:44] = data_mac(keys["data"], 0x100, 7, raw) + b"\0\0\0\x07"
    node = bytearray(56)
    node[:16], node[16:32] = uuid_bytes(0x11), uuid_bytes(0x22)
    node[32:40] = bytes((2, 2, 2, 3, 1, 4, 0, 0))
    put(node, 40, 123, 8)
    put(node, 48, 5)
    node[52:56] = bytes((1, 1, 1, 0))
    plan = bytearray(56)
    plan[:16], plan[16:32], plan[32:48] = uuid_bytes(0x11), uuid_bytes(0x22), uuid_bytes(0x77)
    plan[48:52] = bytes((1, 2, 1, 0))
    put(plan, 52, 200)  # test value, not a product timing policy
    receipt = bytearray(40)
    receipt[:16], receipt[16:32] = uuid_bytes(0x11), uuid_bytes(0x22)
    receipt[32] = 1
    put(receipt, 36, 1)
    incident = bytearray(104)
    incident[:16], incident[16:32] = uuid_bytes(0x33), uuid_bytes(0x66)
    incident[32:36] = bytes((2, 1, 0, 3))
    for at, value in ((36, 1), (40, 1), (44, 1000), (48, 20)):
        put(incident, at, value)
    put(incident, 56, 0x100, 2)
    put(incident, 58, 4, 2)
    incident[60:] = reference
    rejection = bytearray(80)
    rejection[:16], rejection[16:32] = uuid_bytes(0x44), uuid_bytes(0x55)
    rejection[32:36] = bytes((7, 1, 1, 0))
    rejection[36:] = reference
    ecu_metrics = bytearray(52)
    ecu_metrics[:16] = uuid_bytes(0x11)
    for at, value in ((16, 1000), (20, 1001), (24, 0xFFFFFFFF), (28, 0xFFFFFFFF),
                      (32, 0xFFFFFFFF), (36, 0xFFFFFFFF), (40, 0xFFFFFFFF), (44, 0xFFFFFFFF), (48, 1)):
        put(ecu_metrics, at, value)
    ivi_metrics = bytearray(52)
    ivi_metrics[:16] = uuid_bytes(0x44)
    for at, value in ((16, 1000), (20, 20), (24, 10), (28, 50), (32, 100000),
                      (36, 110000), (40, 0), (44, 0), (48, 127)):
        put(ivi_metrics, at, value)
    observation = bytearray(52)
    observation[:16] = uuid_bytes(0x33)
    observation[16] = 1
    put(observation, 20, 1)
    put(observation, 24, 1000, 8)
    for at, value in ((32, 1000), (36, 20), (40, 0), (44, 1000)):
        put(observation, at, value)
    observation[48:52] = bytes((2, 0, 3, 0))
    packets = [
        ("node", 0x302, 0, 1, node), ("plan", 0x302, 1, 2, plan),
        ("receipt", 0x303, 0, 3, receipt), ("incident", 0x302, 2, 4, incident),
        ("rejection", 0x303, 1, 5, rejection), ("ecu_metrics", 0x302, 3, 6, ecu_metrics),
        ("ivi_metrics", 0x303, 2, 6, ivi_metrics), ("observation", 0x302, 4, 7, observation)]
    return ctx, keys, [(name, sender, sequence, kind, bytes(body)) for name, sender, sequence, kind, body in packets]


def dummy_vectors():
    ctx, keys, packets = fixtures()
    out = {"context": context_id(ctx).hex(), "key.diag-ecu": keys["diag-ecu"].hex(), "key.diag-ivi": keys["diag-ivi"].hex()}
    for name, sender, sequence, kind, body in packets:
        frames = encode(keys, ctx, sender, sequence, kind, body)
        envelope = b"".join(data[4:] for _, data in frames)[:38+len(body)]
        out["envelope."+name] = envelope.hex()
        out["tag."+name] = envelope[-16:].hex()
        for i, (can_id, data) in enumerate(frames):
            out[f"frame.{name}.{i}"] = f"{can_id}:{data.hex()}"
    return out
