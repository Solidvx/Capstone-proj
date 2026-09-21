#pragma once

#include "can_driver.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

class SecOcModule {
public:
    static constexpr std::size_t kKeySize = 32;

    bool loadKey(const std::string& path);
    void setKey(const std::array<uint8_t, kKeySize>& key);

    CanFrame sign(uint32_t auth_can_id, uint32_t original_can_id, const std::array<uint8_t, 8>& payload);
    bool verify(uint32_t original_can_id, const std::array<uint8_t, 8>& payload, const CanFrame& auth_frame);
    uint32_t nextCounter() const;
    void resetCounter(uint32_t counter = 0);

private:
    std::array<uint8_t, 4> computeMac(
        uint32_t original_can_id,
        uint32_t rolling_counter,
        const std::array<uint8_t, 8>& payload) const;

    bool hasKey() const;

    std::vector<uint8_t> key_;
    uint32_t counter_ = 0;
    std::optional<uint32_t> last_verified_counter_;
};
