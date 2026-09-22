#include "secoc_verifier.h"

#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>

#include <algorithm>
#include <array>
#include <stdexcept>

namespace ivi {
namespace {

void writeU32Be(std::uint8_t* output, std::uint32_t value) {
    output[0] = static_cast<std::uint8_t>((value >> 24U) & 0xFFU);
    output[1] = static_cast<std::uint8_t>((value >> 16U) & 0xFFU);
    output[2] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
    output[3] = static_cast<std::uint8_t>(value & 0xFFU);
}

}  // namespace

SecOcVerifier::SecOcVerifier(SecOcKey key) : key_(key) {}

TruncatedMac SecOcVerifier::computeTruncatedMac(std::uint16_t can_id,
                                                std::uint32_t rolling_counter,
                                                const CanPayload& payload) const {
    std::array<std::uint8_t, 14> input{};
    input[0] = static_cast<std::uint8_t>((can_id >> 8U) & 0xFFU);
    input[1] = static_cast<std::uint8_t>(can_id & 0xFFU);
    writeU32Be(&input[2], rolling_counter);
    std::copy(payload.begin(), payload.end(), input.begin() + 6);

    std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
    unsigned int digest_size = 0;
    if (HMAC(EVP_sha256(), key_.data(), static_cast<int>(key_.size()), input.data(),
             input.size(), digest.data(), &digest_size) == nullptr || digest_size < 4U) {
        throw std::runtime_error("HMAC-SHA256 calculation failed");
    }
    return {digest[0], digest[1], digest[2], digest[3]};
}

SecOcResult SecOcVerifier::verify(
    std::uint16_t can_id,
    std::uint32_t rolling_counter,
    const CanPayload& payload,
    const TruncatedMac& received_mac,
    std::optional<std::uint32_t> last_accepted_counter) const {
    SecOcResult result;
    result.expected_mac = computeTruncatedMac(can_id, rolling_counter, payload);
    result.mac_valid = CRYPTO_memcmp(
                           result.expected_mac.data(), received_mac.data(), received_mac.size()) == 0;

    if (!last_accepted_counter.has_value()) {
        result.counter_valid = true;
    } else {
        const std::uint32_t delta = rolling_counter - *last_accepted_counter;
        result.counter_valid = delta >= 1U && delta <= 100U;
    }
    result.accepted = result.mac_valid && result.counter_valid;
    return result;
}

}  // namespace ivi
