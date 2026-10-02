#include "can_publisher.h"
#include "secoc_module.h"

#include <gtest/gtest.h>

#include <array>

namespace {
std::array<uint8_t, SecOcModule::kKeySize> testKey() {
    std::array<uint8_t, SecOcModule::kKeySize> key{};
    for (std::size_t i = 0; i < key.size(); ++i) {
        key[i] = static_cast<uint8_t>(i);
    }
    return key;
}
}

TEST(SecOcModule, SignsKnownCounterZeroVector) {
    SecOcModule secoc;
    secoc.setKey(testKey());
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});

    const auto auth = secoc.sign(0x102, 0x100, status.data);

    EXPECT_EQ(auth.id, 0x102U);
    EXPECT_EQ(auth.dlc, 8);
    EXPECT_EQ(auth.data[0], 0xD0);
    EXPECT_EQ(auth.data[1], 0xDD);
    EXPECT_EQ(auth.data[2], 0xFC);
    EXPECT_EQ(auth.data[3], 0x05);
    EXPECT_EQ(auth.data[4], 0x00);
    EXPECT_EQ(auth.data[5], 0x00);
    EXPECT_EQ(auth.data[6], 0x00);
    EXPECT_EQ(auth.data[7], 0x00);
}

TEST(SecOcModule, VerifiesAndRejectsTamper) {
    SecOcModule signer;
    SecOcModule verifier;
    signer.setKey(testKey());
    verifier.setKey(testKey());
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});
    auto auth = signer.sign(0x102, 0x100, status.data);

    EXPECT_TRUE(verifier.verify(0x100, status.data, auth));

    auth.data[0] ^= 0xFF;
    EXPECT_FALSE(verifier.verify(0x100, status.data, auth));
}

TEST(SecOcModule, RejectsReplayCounter) {
    SecOcModule signer;
    SecOcModule verifier;
    signer.setKey(testKey());
    verifier.setKey(testKey());
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});
    const auto auth = signer.sign(0x102, 0x100, status.data);

    EXPECT_TRUE(verifier.verify(0x100, status.data, auth));
    EXPECT_FALSE(verifier.verify(0x100, status.data, auth));
}

TEST(SecOcModule, CounterIncrementsAcrossMessages) {
    SecOcModule signer;
    signer.setKey(testKey());
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});

    const auto first = signer.sign(0x102, 0x100, status.data);
    const auto second = signer.sign(0x102, 0x100, status.data);

    EXPECT_EQ(first.data[7], 0x00);
    EXPECT_EQ(second.data[7], 0x01);
    EXPECT_EQ(signer.nextCounter(0x102), 2U);
}

// ICD 1.4/2.4: 0x102 and 0x103 keep independent counters, so a rare Fail-safe
// event stays inside the receiver window however many BMS frames came before.
TEST(SecOcModule, CountersAreIndependentPerAuthenticatedStream) {
    SecOcModule signer;
    SecOcModule verifier;
    signer.setKey(testKey());
    verifier.setKey(testKey());
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});
    const auto warning = encodeFailSafeFrame({0, 1, 0x01, 19.5f, 25});

    const auto first_event = signer.sign(0x103, 0x101, warning.data);
    EXPECT_TRUE(verifier.verify(0x101, warning.data, first_event));
    for (int i = 0; i < 150; ++i) {
        const auto bms = signer.sign(0x102, 0x100, status.data);
        EXPECT_TRUE(verifier.verify(0x100, status.data, bms));
    }
    const auto second_event = signer.sign(0x103, 0x101, warning.data);

    EXPECT_EQ(first_event.data[7], 0x00);
    EXPECT_EQ(second_event.data[7], 0x01);
    EXPECT_EQ(signer.nextCounter(0x102), 150U);
    EXPECT_EQ(signer.nextCounter(0x103), 2U);
    EXPECT_TRUE(verifier.verify(0x101, warning.data, second_event));
}

TEST(SecOcModule, AcceptsCounterWrap) {
    SecOcModule signer;
    SecOcModule verifier;
    signer.setKey(testKey());
    verifier.setKey(testKey());
    signer.resetCounter(0x102, 0xFFFFFFFFU);
    const auto status = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});

    const auto last_before_wrap = signer.sign(0x102, 0x100, status.data);
    const auto wrapped = signer.sign(0x102, 0x100, status.data);

    EXPECT_TRUE(verifier.verify(0x100, status.data, last_before_wrap));
    EXPECT_TRUE(verifier.verify(0x100, status.data, wrapped));
    EXPECT_EQ(wrapped.data[4], 0x00);
    EXPECT_EQ(wrapped.data[5], 0x00);
    EXPECT_EQ(wrapped.data[6], 0x00);
    EXPECT_EQ(wrapped.data[7], 0x00);
}


namespace {
// Public dummy-key HMAC vectors, identical to Python boundary fixtures.
CanFrame boundaryFrame(uint32_t counter) {
    CanFrame frame{};
    frame.id = 0x102;
    frame.dlc = 8;
    switch (counter) {
    case 0U: frame.data = {0xD0, 0xDD, 0xFC, 0x05, 0x00, 0x00, 0x00, 0x00}; break;
    case 42U: frame.data = {0xA4, 0xB9, 0xA2, 0xA6, 0x00, 0x00, 0x00, 0x2A}; break;
    case 55U: frame.data = {0x96, 0x67, 0x3A, 0x5E, 0x00, 0x00, 0x00, 0x37}; break;
    case 56U: frame.data = {0x31, 0x00, 0x4D, 0xC0, 0x00, 0x00, 0x00, 0x38}; break;
    case 155U: frame.data = {0xF5, 0x71, 0xEB, 0x03, 0x00, 0x00, 0x00, 0x9B}; break;
    case 156U: frame.data = {0xE5, 0x11, 0x41, 0xF1, 0x00, 0x00, 0x00, 0x9C}; break;
    default: ADD_FAILURE() << "Unknown boundary fixture"; break;
    }
    return frame;
}
const std::array<uint8_t, 8> boundaryPayload{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
}

TEST(SecOcModule, WindowBoundariesPreserveStateOnRejection) {
    struct Case { uint32_t counter; bool accepted; };
    const Case cases[] = {{55, false}, {56, true}, {155, true},
                          {156, false}, {42, false}, {0, false}};
    for (const auto& item : cases) {
        SCOPED_TRACE(item.counter);
        SecOcModule verifier;
        verifier.setKey(testKey());
        ASSERT_TRUE(verifier.verify(0x100, boundaryPayload, boundaryFrame(55)));
        EXPECT_EQ(verifier.verify(0x100, boundaryPayload, boundaryFrame(item.counter)), item.accepted);
        if (!item.accepted) {
            EXPECT_TRUE(verifier.verify(0x100, boundaryPayload, boundaryFrame(56)));
        }
    }
}

TEST(SecOcModule, InvalidMacInsideWindowDoesNotConsumeCounter) {
    SecOcModule verifier;
    verifier.setKey(testKey());
    ASSERT_TRUE(verifier.verify(0x100, boundaryPayload, boundaryFrame(55)));
    auto bad = boundaryFrame(56);
    bad.data[0] ^= 1;
    EXPECT_FALSE(verifier.verify(0x100, boundaryPayload, bad));
    EXPECT_TRUE(verifier.verify(0x100, boundaryPayload, boundaryFrame(56)));
}

TEST(SecOcModule, LegacyFreshReceiverAcceptsOldMacLimitation) {
    // Limitation characterization, not final reboot replay-protection acceptance.
    for (const uint32_t old_counter : {42U, 0U}) {
        SecOcModule verifier;
        verifier.setKey(testKey());
        EXPECT_TRUE(verifier.verify(0x100, boundaryPayload, boundaryFrame(old_counter)));
        EXPECT_FALSE(verifier.verify(0x100, boundaryPayload, boundaryFrame(old_counter)));
    }
}
