#include "vehicle_data_service.h"
#include "test_support.h"

#include <chrono>

namespace {

ivi::SecOcKey dummyKey() {
    ivi::SecOcKey key{};
    for (std::size_t index = 0; index < key.size(); ++index) {
        key[index] = static_cast<std::uint8_t>(index);
    }
    return key;
}

ivi::CanPayload authPayload(const ivi::SecOcVerifier& verifier,
                            std::uint16_t can_id,
                            std::uint32_t counter,
                            const ivi::CanPayload& payload) {
    const auto mac = verifier.computeTruncatedMac(can_id, counter, payload);
    return {mac[0], mac[1], mac[2], mac[3],
            static_cast<std::uint8_t>((counter >> 24U) & 0xFFU),
            static_cast<std::uint8_t>((counter >> 16U) & 0xFFU),
            static_cast<std::uint8_t>((counter >> 8U) & 0xFFU),
            static_cast<std::uint8_t>(counter & 0xFFU)};
}

void testOrphanAndTimeout(const ivi::SecOcVerifier& signer,
                          const ivi::CanPayload& bms) {
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    const auto auth = authPayload(signer, ivi::kCanIdBmsStatus, 0, bms);

    ivi::VehicleDataService orphan_service(dummyKey());
    EXPECT_EQ(orphan_service.processFrame(ivi::kCanIdBmsSecOc, auth, base),
              ivi::ProcessResult::kRejected);
    EXPECT_EQ(orphan_service.latest().orphan_auth_count, 1U);
    EXPECT_FALSE(orphan_service.latest().vehicle.valid);

    ivi::VehicleDataService boundary_service(dummyKey());
    boundary_service.processFrame(ivi::kCanIdBmsStatus, bms, base);
    EXPECT_EQ(boundary_service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  auth,
                  base + ivi::VehicleDataService::kPendingTimeout -
                      std::chrono::milliseconds{1}),
              ivi::ProcessResult::kPublished);

    ivi::VehicleDataService expired_service(dummyKey());
    expired_service.processFrame(ivi::kCanIdBmsStatus, bms, base);
    EXPECT_EQ(expired_service.processFrame(ivi::kCanIdBmsSecOc,
                                           auth,
                                           base + std::chrono::milliseconds{1}),
              ivi::ProcessResult::kPublished);
    auto changed_bms = bms;
    changed_bms[0] = 0x28;
    const auto changed_auth = authPayload(signer, ivi::kCanIdBmsStatus, 1, changed_bms);
    const auto second_raw_time = base + std::chrono::milliseconds{200};
    expired_service.processFrame(ivi::kCanIdBmsStatus, changed_bms, second_raw_time);
    EXPECT_EQ(expired_service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  changed_auth,
                  second_raw_time + ivi::VehicleDataService::kPendingTimeout),
              ivi::ProcessResult::kRejected);
    auto expired = expired_service.latest();
    EXPECT_EQ(expired.pending_timeout_count, 1U);
    EXPECT_EQ(expired.secoc_failure_count, 1U);
    EXPECT_TRUE(expired.vehicle.valid);
    EXPECT_NEAR(expired.vehicle.soc_percent, 75.0, 0.001);

    EXPECT_EQ(expired_service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  changed_auth,
                  second_raw_time + ivi::VehicleDataService::kPendingTimeout +
                      std::chrono::milliseconds{1}),
              ivi::ProcessResult::kRejected);
    EXPECT_EQ(expired_service.latest().orphan_auth_count, 1U);
}

void testReplacement(const ivi::SecOcVerifier& signer,
                     const ivi::CanPayload& original_bms) {
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    auto newer_bms = original_bms;
    newer_bms[0] = 0x28;

    ivi::VehicleDataService service(dummyKey());
    service.processFrame(ivi::kCanIdBmsStatus, original_bms, base);
    service.processFrame(
        ivi::kCanIdBmsStatus, newer_bms, base + std::chrono::milliseconds{10});
    EXPECT_EQ(service.latest().pending_overwrite_count, 1U);

    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  authPayload(signer, ivi::kCanIdBmsStatus, 0, original_bms),
                  base + std::chrono::milliseconds{20}),
              ivi::ProcessResult::kRejected);
    EXPECT_FALSE(service.latest().vehicle.valid);

    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  authPayload(signer, ivi::kCanIdBmsStatus, 0, newer_bms),
                  base + std::chrono::milliseconds{30}),
              ivi::ProcessResult::kPublished);
    EXPECT_NEAR(service.latest().vehicle.soc_percent, 20.0, 0.001);
    EXPECT_EQ(service.latest().consecutive_secoc_failure_count, 0U);
}

void testInterleavedPairs(const ivi::SecOcVerifier& signer,
                          const ivi::CanPayload& bms) {
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    const ivi::CanPayload fail_safe{0x00, 0x02, 0x02, 0x09, 0x41, 0, 0, 0};
    ivi::VehicleDataService service(dummyKey());

    service.processFrame(ivi::kCanIdBmsStatus, bms, base);
    service.processFrame(
        ivi::kCanIdBmsFailSafe, fail_safe, base + std::chrono::milliseconds{1});
    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdFailSafeSecOc,
                  authPayload(signer, ivi::kCanIdBmsFailSafe, 77, fail_safe),
                  base + std::chrono::milliseconds{2}),
              ivi::ProcessResult::kPublished);
    EXPECT_EQ(service.latest().vehicle.fail_safe_state, 2U);
    EXPECT_FALSE(service.latest().vehicle.valid);

    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  authPayload(signer, ivi::kCanIdBmsStatus, 7, bms),
                  base + std::chrono::milliseconds{3}),
              ivi::ProcessResult::kPublished);
    EXPECT_TRUE(service.latest().vehicle.valid);
    EXPECT_EQ(service.latest().vehicle.fail_safe_state, 2U);
}

void testFailureEscalationAndRecovery(const ivi::SecOcVerifier& signer,
                                      const ivi::CanPayload& bms) {
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    ivi::VehicleDataService service(dummyKey());
    service.processFrame(ivi::kCanIdBmsStatus, bms, base);
    auto bad_auth = authPayload(signer, ivi::kCanIdBmsStatus, 0, bms);
    bad_auth[0] ^= 0x01;

    for (int attempt = 0; attempt < 4; ++attempt) {
        EXPECT_EQ(service.processFrame(ivi::kCanIdBmsSecOc,
                                       bad_auth,
                                       base + std::chrono::milliseconds{attempt + 1}),
                  ivi::ProcessResult::kRejected);
    }
    auto failed = service.latest();
    EXPECT_EQ(failed.consecutive_secoc_failure_count, 4U);
    EXPECT_TRUE(failed.last_message.find("WARNING:") == 0U);
    EXPECT_FALSE(failed.vehicle.valid);

    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdBmsSecOc,
                  authPayload(signer, ivi::kCanIdBmsStatus, 0, bms),
                  base + std::chrono::milliseconds{10}),
              ivi::ProcessResult::kPublished);
    EXPECT_EQ(service.latest().consecutive_secoc_failure_count, 0U);
}

void run() {
    const auto key = dummyKey();
    const ivi::SecOcVerifier signer(key);
    const ivi::CanPayload bms{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};

    testOrphanAndTimeout(signer, bms);
    testReplacement(signer, bms);
    testInterleavedPairs(signer, bms);
    testFailureEscalationAndRecovery(signer, bms);
}

}  // namespace

int main() {
    return runTestProgram("VehicleDataService P2 security policy", run);
}
