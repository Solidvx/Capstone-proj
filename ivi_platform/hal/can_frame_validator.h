#pragma once

#include <cstdint>

namespace ivi {

constexpr std::uint32_t kCanEffFlag = 0x80000000U;
constexpr std::uint32_t kCanRtrFlag = 0x40000000U;
constexpr std::uint32_t kCanErrFlag = 0x20000000U;
constexpr std::uint32_t kCanSffMask = 0x000007FFU;

enum class CanFrameValidation {
    kAccepted,
    kExtendedFrame,
    kRemoteFrame,
    kErrorFrame,
    kInvalidLength,
    kUnsupportedId,
};

CanFrameValidation validateClassicCanFrame(std::uint32_t raw_can_id, std::uint8_t dlc);

}  // namespace ivi
