"""CAN 물리한계·SecOC 실측치 계산/측정 (의존성 0, 순수 Python).

보안 모델 개선안(`tmp/보안모델_확장_개선안.md` §1)의 근거 숫자를 재현한다.
실행: python security/analysis/measure_can_secoc.py
"""

from __future__ import annotations

import hashlib
import hmac
import sys
import time

try:  # Windows 콘솔(cp949)에서 유니코드 출력 보호
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BITRATE = 500_000  # 500 kbps Classic CAN (SDD-IVI §3.3)


def frame_bits(dlc: int, worst_case_stuffing: bool = True) -> int:
    """CAN 2.0A 표준 데이터 프레임 비트 수.

    SOF(1)+arb(12)+ctrl(6)+data(8*dlc)+CRC(16)+ACK(2)+EOF(7)+IFS(3).
    비트 스터핑은 SOF..CRC 구간에 최악 (region-1)//4 비트 추가.
    """
    base = 1 + 12 + 6 + dlc * 8 + 16 + 2 + 7 + 3
    if not worst_case_stuffing:
        return base
    stuff_region = 1 + 12 + 6 + dlc * 8 + 15
    return base + (stuff_region - 1) // 4


def max_frames_per_sec(dlc: int, worst_case_stuffing: bool = True) -> float:
    return BITRATE / frame_bits(dlc, worst_case_stuffing)


def secoc_stream_bus_load_pct(period_ms: float = 100.0, dlc: int = 8) -> float:
    """인증 스트림(원본+MAC 프레임 각 1개)의 버스 부하 %."""
    fps = 2 * (1000.0 / period_ms)  # 원본 + 0x102
    return fps * frame_bits(dlc) / BITRATE * 100.0


def mac_forgery_days(rate_fps: float, mac_bits: int = 32) -> float:
    """절단 MAC(mac_bits) 무차별 위조 시 기대 첫 성공까지 연속 공격 일수."""
    expected_attempts = 2 ** mac_bits
    return expected_attempts / rate_fps / 86400.0


def measure_hmac_us(n: int = 20000) -> float:
    """HMAC-SHA256(4B 절단) 1건 계산 시간(µs) 실측."""
    key = bytes(range(32))
    payload = bytes.fromhex("96BE1068FFEC4100")

    def mac(can_id: int, counter: int) -> bytes:
        data = can_id.to_bytes(2, "big") + counter.to_bytes(4, "big") + payload
        return hmac.new(key, data, hashlib.sha256).digest()[:4]

    t0 = time.perf_counter()
    for i in range(n):
        mac(0x100, i & 0xFFFFFFFF)
    return (time.perf_counter() - t0) / n * 1e6


def main() -> None:
    print("=" * 64)
    print("CAN / SecOC 실측치  (500 kbps Classic CAN)")
    print("=" * 64)

    print("\n[1] 최대 프레임/초 (Flooding 상한)")
    for dlc in (8, 0):
        for worst in (False, True):
            b = frame_bits(dlc, worst)
            fps = max_frames_per_sec(dlc, worst)
            tag = "worst-stuff" if worst else "no-stuff   "
            print(f"    DLC={dlc}B {tag}: {b:3d} bit/frame -> {fps:8.0f} fps "
                  f"({b / BITRATE * 1e6:5.1f} us)")
    print("    => 8B 프레임으로 '>=5,000 fps' 물리 불가. bus-load% 지표로 재정의할 것.")

    print("\n[2] SecOC 인증 스트림 버스 부하 (0x100+0x102, 100ms)")
    print(f"    = {secoc_stream_bus_load_pct():.3f} %  (프레임 수 2배화, 부하는 무시가능)")

    print("\n[3] 4B 절단 MAC 위조 위험 (rate 기반)")
    print(f"    시도당 성공확률 = 2^-32 = {2 ** -32:.3e}")
    for rate, label in ((max_frames_per_sec(8), "8B 최대 flooding"),
                        (max_frames_per_sec(0), "0B 최대")):
        print(f"    {label} ({rate:.0f} fps): 기대 첫 위조까지 "
              f"{mac_forgery_days(rate):.1f} 일 연속")
    print("    => auth-failure lockout(예: 실패 10회->차단) 도입 시 사실상 불가.")

    print("\n[4] HMAC-SHA256 MAC 계산 지연 (실측)")
    us = measure_hmac_us()
    print(f"    MAC 1건 = {us:.2f} us  (100ms 주기의 {us / 1000 / 100 * 100:.4f}%)")
    a = hmac.new(bytes(range(32)), b"x" * 14, hashlib.sha256).digest()[:4]
    b = bytes([a[0] ^ 0xFF]) + a[1:]
    print(f"    상수시간 비교(compare_digest): 정상={hmac.compare_digest(a, a)}, "
          f"변조거부={not hmac.compare_digest(a, b)}")


if __name__ == "__main__":
    main()
