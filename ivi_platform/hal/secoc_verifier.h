#pragma once

#include <cstdint>
#include <optional>

#include "can_types.h"

namespace ivi {

struct SecOcResult {
    bool accepted = false;
    bool mac_valid = false;
    bool counter_valid = false;
    TruncatedMac expected_mac{};
};

class SecOcVerifier {
public:
    explicit SecOcVerifier(SecOcKey key);

    TruncatedMac computeTruncatedMac(std::uint16_t can_id,
                                     std::uint32_t rolling_counter,
                                     const CanPayload& payload) const;

    SecOcResult verify(std::uint16_t can_id,
                       std::uint32_t rolling_counter,
                       const CanPayload& payload,
                       const TruncatedMac& received_mac,
                       std::optional<std::uint32_t> last_accepted_counter) const;

private:
    SecOcKey key_;
};

}  // namespace ivi
