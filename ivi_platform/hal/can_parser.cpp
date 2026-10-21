#include "can_parser.h"

namespace ivi {
namespace {

std::uint16_t readU16Be(const std::uint8_t* bytes) {
    return static_cast<std::uint16_t>(
        (static_cast<std::uint16_t>(bytes[0]) << 8U) |
        static_cast<std::uint16_t>(bytes[1]));
}

std::int16_t readI16Be(const std::uint8_t* bytes) {
    return static_cast<std::int16_t>(readU16Be(bytes));
}

std::uint32_t readU32Be(const std::uint8_t* bytes) {
    return (static_cast<std::uint32_t>(bytes[0]) << 24U) |
           (static_cast<std::uint32_t>(bytes[1]) << 16U) |
           (static_cast<std::uint32_t>(bytes[2]) << 8U) |
           static_cast<std::uint32_t>(bytes[3]);
}

}  // namespace

std::optional<BmsStatus> parseBmsStatus(const CanPayload& payload) {
    if (payload[0] > 200U || payload[1] > 200U || payload[6] > 165U || payload[7] != 0U) {
        return std::nullopt;
    }
    return BmsStatus{
        static_cast<double>(payload[0]) * 0.5,
        static_cast<double>(payload[1]) * 0.5,
        static_cast<double>(readU16Be(&payload[2])) * 0.01,
        static_cast<double>(readI16Be(&payload[4])) * 0.1,
        static_cast<double>(payload[6]) - 40.0,
    };
}

std::optional<FailSafeEvent> parseFailSafeEvent(const CanPayload& payload) {
    if (payload[0] > 3U || payload[1] > 3U || payload[2] < 1U || payload[2] > 7U || payload[3] > 200U ||
        payload[4] > 165U || payload[5] != 0U || payload[6] != 0U || payload[7] != 0U) {
        return std::nullopt;
    }
    return FailSafeEvent{
        payload[0],
        payload[1],
        payload[2],
        static_cast<double>(payload[3]) * 0.5,
        static_cast<double>(payload[4]) - 40.0,
    };
}

std::optional<SecOcAuth> parseSecOcAuth(const CanPayload& payload) {
    return SecOcAuth{{payload[0], payload[1], payload[2], payload[3]}, readU32Be(&payload[4])};
}

std::optional<SecurityAlert> parseIdsAlert(const CanPayload& payload) {
    if (payload[0] > 4U) {
        return std::nullopt;
    }
    return SecurityAlert{
        payload[0],
        static_cast<double>(payload[1]) * 0.01,
        readU16Be(&payload[2]),
        readU32Be(&payload[4]),
    };
}

bool isSupportedCanId(std::uint32_t can_id) {
    return can_id == kCanIdBmsStatus || can_id == kCanIdBmsFailSafe ||
           can_id == kCanIdBmsSecOc || can_id == kCanIdFailSafeSecOc ||
           can_id == kCanIdIdsAlert;
}

const char* failSafeStateName(std::uint8_t state) {
    switch (state) {
        case 0: return "NORMAL";
        case 1: return "WARNING";
        case 2: return "CRITICAL";
        case 3: return "SHUTDOWN";
        default: return "UNKNOWN";
    }
}

const char* failSafeReasonName(std::uint8_t reason) {
    switch (reason) {
        case 0x00: return "NONE";
        case 0x01: return "SOC_BELOW_20";
        case 0x02: return "SOC_BELOW_5";
        case 0x03: return "TEMPERATURE_ABOVE_55";
        case 0x04: return "TEMPERATURE_ABOVE_60";
        case 0x05: return "RECOVERED";
        case 0x06: return "MANUAL_RESET";
        case 0x07: return "WATCHDOG_RESTART_FAILED";
        default: return "UNKNOWN";
    }
}

const char* sensorStateName(std::uint8_t state) {
    switch (state) {
        case 0: return "UNSUPPORTED_LEGACY_WIRE";
        case 1: return "INITIALIZING";
        case 2: return "NORMAL";
        case 3: return "ERROR_NO_LAST_GOOD";
        case 4: return "ERROR_USING_LAST_GOOD";
        case 5: return "RECOVERING_NO_LAST_GOOD";
        case 6: return "RECOVERING_USING_LAST_GOOD";
        default: return "UNSUPPORTED_CODE";
    }
}

const char* attackTypeName(std::uint8_t attack_type) {
    switch (attack_type) {
        case 0: return "None";
        case 1: return "Fuzzy";
        case 2: return "Replay";
        case 3: return "Spoofing";
        case 4: return "Flooding";
        default: return "Unknown";
    }
}

}  // namespace ivi
