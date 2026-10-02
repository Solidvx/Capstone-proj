#pragma once

#include "can_driver.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

// RollingCounter is independent per authenticated stream (ICD 1.4/2.4):
// 0x102 for 0x100 and 0x103 for 0x101 never share a counter.
class SecOcModule {
public:
    static constexpr std::size_t kKeySize = 32;

    bool loadKey(const std::string& path);
    void setKey(const std::array<uint8_t, kKeySize>& key);

    CanFrame sign(uint32_t auth_can_id, uint32_t original_can_id, const std::array<uint8_t, 8>& payload);
    // Window state is kept per original CAN ID.
    bool verify(uint32_t original_can_id, const std::array<uint8_t, 8>& payload, const CanFrame& auth_frame);
    uint32_t nextCounter(uint32_t auth_can_id) const;
    void resetCounter(uint32_t auth_can_id, uint32_t counter = 0);

private:
    std::array<uint8_t, 4> computeMac(
        uint32_t original_can_id,
        uint32_t rolling_counter,
        const std::array<uint8_t, 8>& payload) const;

    bool hasKey() const;

    std::vector<uint8_t> key_;
    std::map<uint32_t, uint32_t> tx_counters_;             // auth CAN ID -> next counter
    std::map<uint32_t, uint32_t> last_verified_counters_;  // original CAN ID -> last accepted
};
