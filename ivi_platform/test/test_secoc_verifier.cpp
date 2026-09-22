#include "secoc_verifier.h"
#include "test_support.h"

#include <limits>

namespace {

ivi::SecOcKey dummyKey() {
    ivi::SecOcKey key{};
    for (std::size_t index = 0; index < key.size(); ++index) {
        key[index] = static_cast<std::uint8_t>(index);
    }
    return key;
}

void run() {
    const ivi::CanPayload payload{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    const ivi::SecOcVerifier verifier(dummyKey());

    const auto known = verifier.computeTruncatedMac(0x100, 0, payload);
    EXPECT_EQ(known[0], 0xD0U);
    EXPECT_EQ(known[1], 0xDDU);
    EXPECT_EQ(known[2], 0xFCU);
    EXPECT_EQ(known[3], 0x05U);

    const auto first = verifier.verify(0x100, 0, payload, known, std::nullopt);
    EXPECT_TRUE(first.accepted);

    const auto plus_100_mac = verifier.computeTruncatedMac(0x100, 100, payload);
    EXPECT_TRUE(verifier.verify(0x100, 100, payload, plus_100_mac, 0).accepted);

    const auto plus_101_mac = verifier.computeTruncatedMac(0x100, 101, payload);
    EXPECT_FALSE(verifier.verify(0x100, 101, payload, plus_101_mac, 0).accepted);
    EXPECT_FALSE(verifier.verify(0x100, 100, payload, plus_100_mac, 100).counter_valid);

    const auto wrapped_mac = verifier.computeTruncatedMac(0x100, 0, payload);
    EXPECT_TRUE(verifier.verify(
        0x100, 0, payload, wrapped_mac, std::numeric_limits<std::uint32_t>::max()).accepted);

    auto tampered = known;
    tampered[0] ^= 0x01;
    const auto tamper_result = verifier.verify(0x100, 1, payload, tampered, 0);
    EXPECT_FALSE(tamper_result.accepted);
    EXPECT_FALSE(tamper_result.mac_valid);
    EXPECT_TRUE(tamper_result.counter_valid);
}

}  // namespace

int main() {
    return runTestProgram("SecOC HMAC and counter boundaries", run);
}
