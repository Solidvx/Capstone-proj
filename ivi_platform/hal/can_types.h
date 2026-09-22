#pragma once

#include <array>
#include <cstdint>

namespace ivi {

constexpr std::uint32_t kCanIdBmsStatus = 0x100;
constexpr std::uint32_t kCanIdBmsFailSafe = 0x101;
constexpr std::uint32_t kCanIdBmsSecOc = 0x102;
constexpr std::uint32_t kCanIdFailSafeSecOc = 0x103;
constexpr std::uint32_t kCanIdIdsAlert = 0x200;
constexpr std::uint16_t kNoSuspectCanId = 0xFFFF;
constexpr std::size_t kClassicCanPayloadSize = 8;

using CanPayload = std::array<std::uint8_t, kClassicCanPayloadSize>;
using TruncatedMac = std::array<std::uint8_t, 4>;
using SecOcKey = std::array<std::uint8_t, 32>;

struct BmsStatus {
    double soc_percent = 0.0;
    double soh_percent = 0.0;
    double voltage_v = 0.0;
    double current_a = 0.0;
    double temperature_c = 0.0;
};

struct FailSafeEvent {
    std::uint8_t previous_state = 0;
    std::uint8_t new_state = 0;
    std::uint8_t reason = 0;
    double soc_percent = 0.0;
    double temperature_c = 0.0;
};

struct SecOcAuth {
    TruncatedMac truncated_mac{};
    std::uint32_t rolling_counter = 0;
};

struct SecurityAlert {
    std::uint8_t attack_type = 0;
    double anomaly_score = 0.0;
    std::uint16_t suspect_can_id = kNoSuspectCanId;
    std::uint32_t source_timestamp = 0;
};

}  // namespace ivi
