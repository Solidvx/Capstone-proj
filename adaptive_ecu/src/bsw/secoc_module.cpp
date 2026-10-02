#include "secoc_module.h"

#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>

#include <algorithm>
#include <array>
#include <fstream>
#include <utility>

namespace {
void writeUint16Be(std::array<uint8_t, 14>& buffer, uint32_t value) {
    buffer[0] = static_cast<uint8_t>((value >> 8) & 0xFF);
    buffer[1] = static_cast<uint8_t>(value & 0xFF);
}

void writeUint32Be(uint8_t* output, uint32_t value) {
    output[0] = static_cast<uint8_t>((value >> 24) & 0xFF);
    output[1] = static_cast<uint8_t>((value >> 16) & 0xFF);
    output[2] = static_cast<uint8_t>((value >> 8) & 0xFF);
    output[3] = static_cast<uint8_t>(value & 0xFF);
}

uint32_t readUint32Be(const uint8_t* input) {
    return (static_cast<uint32_t>(input[0]) << 24) |
           (static_cast<uint32_t>(input[1]) << 16) |
           (static_cast<uint32_t>(input[2]) << 8) |
           static_cast<uint32_t>(input[3]);
}
}

bool SecOcModule::loadKey(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return false;
    }

    std::vector<uint8_t> key(kKeySize);
    input.read(reinterpret_cast<char*>(key.data()), static_cast<std::streamsize>(key.size()));
    if (input.gcount() != static_cast<std::streamsize>(kKeySize)) {
        return false;
    }

    key_ = std::move(key);
    return true;
}

void SecOcModule::setKey(const std::array<uint8_t, kKeySize>& key) {
    key_.assign(key.begin(), key.end());
}

CanFrame SecOcModule::sign(
    uint32_t auth_can_id,
    uint32_t original_can_id,
    const std::array<uint8_t, 8>& payload) {
    CanFrame frame{};
    frame.id = auth_can_id;
    if (!hasKey()) {
        return frame;
    }

    uint32_t& next = tx_counters_[auth_can_id];
    const uint32_t rolling_counter = next++;
    const auto mac = computeMac(original_can_id, rolling_counter, payload);

    frame.dlc = 8;
    std::copy(mac.begin(), mac.end(), frame.data.begin());
    writeUint32Be(&frame.data[4], rolling_counter);
    return frame;
}

bool SecOcModule::verify(
    uint32_t original_can_id,
    const std::array<uint8_t, 8>& payload,
    const CanFrame& auth_frame) {
    if (!hasKey() || auth_frame.dlc != 8) {
        return false;
    }

    const uint32_t rolling_counter = readUint32Be(&auth_frame.data[4]);
    const auto last = last_verified_counters_.find(original_can_id);
    if (last != last_verified_counters_.end()) {
        const uint32_t delta = rolling_counter - last->second;
        if (delta == 0U || delta > 100U) {
            return false;
        }
    }

    const auto expected = computeMac(original_can_id, rolling_counter, payload);
    if (CRYPTO_memcmp(expected.data(), auth_frame.data.data(), expected.size()) != 0) {
        return false;
    }

    last_verified_counters_[original_can_id] = rolling_counter;
    return true;
}

uint32_t SecOcModule::nextCounter(uint32_t auth_can_id) const {
    const auto it = tx_counters_.find(auth_can_id);
    return it == tx_counters_.end() ? 0U : it->second;
}

void SecOcModule::resetCounter(uint32_t auth_can_id, uint32_t counter) {
    tx_counters_[auth_can_id] = counter;
}

std::array<uint8_t, 4> SecOcModule::computeMac(
    uint32_t original_can_id,
    uint32_t rolling_counter,
    const std::array<uint8_t, 8>& payload) const {
    std::array<uint8_t, 14> input{};
    writeUint16Be(input, original_can_id);
    writeUint32Be(&input[2], rolling_counter);
    std::copy(payload.begin(), payload.end(), input.begin() + 6);

    std::array<uint8_t, EVP_MAX_MD_SIZE> digest{};
    unsigned int digest_len = 0;
    HMAC(
        EVP_sha256(),
        key_.data(),
        static_cast<int>(key_.size()),
        input.data(),
        input.size(),
        digest.data(),
        &digest_len);

    std::array<uint8_t, 4> truncated{};
    std::copy_n(digest.begin(), truncated.size(), truncated.begin());
    return truncated;
}

bool SecOcModule::hasKey() const {
    return key_.size() == kKeySize;
}
