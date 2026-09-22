#include "vehicle_data_service.h"
#include "test_support.h"

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

void run() {
    const auto key = dummyKey();
    const ivi::SecOcVerifier signer(key);
    ivi::VehicleDataService service(key);
    int notifications = 0;
    const auto observer = service.registerObserver(
        [&notifications](const ivi::VehicleSnapshot&) { ++notifications; });
    EXPECT_TRUE(observer != 0U);

    const ivi::CanPayload bms{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsStatus, bms),
              ivi::ProcessResult::kPendingAuthentication);
    EXPECT_FALSE(service.latest().vehicle.valid);
    EXPECT_EQ(notifications, 0);

    const auto bms_auth = authPayload(signer, 0x100, 0, bms);
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsSecOc, bms_auth),
              ivi::ProcessResult::kPublished);
    auto snapshot = service.latest();
    EXPECT_TRUE(snapshot.vehicle.valid);
    EXPECT_FALSE(snapshot.vehicle.stale);
    EXPECT_NEAR(snapshot.vehicle.soc_percent, 75.0, 0.001);
    EXPECT_EQ(notifications, 1);

    auto changed_bms = bms;
    changed_bms[0] = 0x28;
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsStatus, changed_bms),
              ivi::ProcessResult::kPendingAuthentication);
    auto bad_auth = authPayload(signer, 0x100, 1, changed_bms);
    bad_auth[0] ^= 0x80;
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsSecOc, bad_auth),
              ivi::ProcessResult::kRejected);
    EXPECT_NEAR(service.latest().vehicle.soc_percent, 75.0, 0.001);
    EXPECT_EQ(notifications, 1);

    const auto good_auth = authPayload(signer, 0x100, 1, changed_bms);
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsSecOc, good_auth),
              ivi::ProcessResult::kPublished);
    EXPECT_NEAR(service.latest().vehicle.soc_percent, 20.0, 0.001);

    const ivi::CanPayload fail_safe{0x00, 0x02, 0x02, 0x09, 0x41, 0, 0, 0};
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsFailSafe, fail_safe),
              ivi::ProcessResult::kPendingAuthentication);
    EXPECT_EQ(service.latest().vehicle.fail_safe_state, 0U);
    EXPECT_EQ(service.processFrame(
                  ivi::kCanIdFailSafeSecOc, authPayload(signer, 0x101, 77, fail_safe)),
              ivi::ProcessResult::kPublished);
    EXPECT_EQ(service.latest().vehicle.fail_safe_state, 2U);

    const ivi::CanPayload ids{0x04, 0x96, 0x01, 0x00, 0, 0, 0, 1};
    EXPECT_EQ(service.processFrame(ivi::kCanIdIdsAlert, ids),
              ivi::ProcessResult::kPublished);
    EXPECT_TRUE(service.latest().security_alert.has_value());

    const auto bms_auth_2 = authPayload(signer, 0x100, 2, bms);
    service.processFrame(ivi::kCanIdBmsStatus, bms);
    service.processFrame(ivi::kCanIdBmsSecOc, bms_auth_2);
    EXPECT_TRUE(service.latest().security_alert.has_value());
    EXPECT_EQ(service.latest().vehicle.fail_safe_state, 2U);

    EXPECT_TRUE(service.unregisterObserver(observer));
    EXPECT_FALSE(service.unregisterObserver(observer));
    const int before = notifications;
    service.processFrame(ivi::kCanIdIdsAlert, ids);
    EXPECT_EQ(notifications, before);
}

}  // namespace

int main() {
    return runTestProgram("VehicleDataService authenticated publication", run);
}
