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

void publishBms(ivi::VehicleDataService& service,
                const ivi::SecOcVerifier& signer,
                const ivi::CanPayload& payload,
                std::uint32_t counter,
                ivi::VehicleDataService::Clock::time_point at) {
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsStatus, payload, at),
              ivi::ProcessResult::kPendingAuthentication);
    EXPECT_EQ(service.processFrame(ivi::kCanIdBmsSecOc,
                                   authPayload(signer, ivi::kCanIdBmsStatus,
                                               counter, payload),
                                   at + std::chrono::milliseconds{1}),
              ivi::ProcessResult::kPublished);
}

void testStaleBoundaryAndLastGood() {
    const auto key = dummyKey();
    const ivi::SecOcVerifier signer(key);
    ivi::VehicleDataService service(key);
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    const ivi::CanPayload bms{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    int notifications = 0;
    service.registerObserver([&notifications](const ivi::VehicleSnapshot&) {
        ++notifications;
    });

    publishBms(service, signer, bms, 0, base);
    EXPECT_EQ(notifications, 1);
    EXPECT_TRUE(service.refreshTime(base + std::chrono::milliseconds{300}));
    auto before_boundary = service.latest();
    EXPECT_FALSE(before_boundary.vehicle.stale);
    EXPECT_EQ(before_boundary.last_good_age_ms, 299U);

    EXPECT_TRUE(service.refreshTime(base + std::chrono::milliseconds{301}));
    auto stale = service.latest();
    EXPECT_TRUE(stale.vehicle.stale);
    EXPECT_EQ(stale.last_good_age_ms, 300U);
    EXPECT_NEAR(stale.vehicle.soc_percent, 75.0, 0.001);
    EXPECT_FALSE(service.refreshTime(base + std::chrono::milliseconds{301}));
}

void testFailSafeDoesNotRefreshBmsAge() {
    const auto key = dummyKey();
    const ivi::SecOcVerifier signer(key);
    ivi::VehicleDataService service(key);
    const auto base = ivi::VehicleDataService::Clock::time_point{};
    const ivi::CanPayload bms{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    const ivi::CanPayload fail_safe{0x00, 0x01, 0x07, 0x96, 0x41, 0, 0, 0};

    publishBms(service, signer, bms, 0, base);
    const auto event_time = base + std::chrono::milliseconds{200};
    service.processFrame(ivi::kCanIdBmsFailSafe, fail_safe, event_time);
    service.processFrame(
        ivi::kCanIdFailSafeSecOc,
        authPayload(signer, ivi::kCanIdBmsFailSafe, 0, fail_safe),
        event_time + std::chrono::milliseconds{1});

    service.refreshTime(base + std::chrono::milliseconds{301});
    const auto snapshot = service.latest();
    EXPECT_TRUE(snapshot.vehicle.stale);
    EXPECT_EQ(snapshot.vehicle.fail_safe_state, 1U);
    EXPECT_EQ(snapshot.vehicle.fail_safe_reason, 7U);
    EXPECT_TRUE(std::string(ivi::failSafeReasonName(7)) ==
                "WATCHDOG_RESTART_FAILED");
}

void testIdsAcknowledgementSequence() {
    ivi::VehicleDataService service(dummyKey());
    const ivi::CanPayload first{0x01, 0x64, 0x01, 0x00, 0, 0, 0, 1};
    const ivi::CanPayload clear{0x00, 0x00, 0xFF, 0xFF, 0, 0, 0, 2};
    const ivi::CanPayload second{0x04, 0x96, 0x01, 0x00, 0, 0, 0, 3};

    EXPECT_EQ(service.processFrame(ivi::kCanIdIdsAlert, first),
              ivi::ProcessResult::kPublished);
    const auto first_sequence = service.latest().security_alert_sequence;
    EXPECT_TRUE(service.latest().security_alert.has_value());

    EXPECT_EQ(service.processFrame(ivi::kCanIdIdsAlert, clear),
              ivi::ProcessResult::kIgnored);
    EXPECT_TRUE(service.latest().security_alert.has_value());

    EXPECT_EQ(service.processFrame(ivi::kCanIdIdsAlert, second),
              ivi::ProcessResult::kPublished);
    const auto second_sequence = service.latest().security_alert_sequence;
    EXPECT_TRUE(second_sequence > first_sequence);
    EXPECT_FALSE(service.acknowledgeSecurityAlert(first_sequence));
    EXPECT_TRUE(service.latest().security_alert.has_value());
    EXPECT_TRUE(service.acknowledgeSecurityAlert(second_sequence));
    EXPECT_FALSE(service.latest().security_alert.has_value());
}

void testSensorStateLabels() {
    EXPECT_TRUE(std::string(ivi::sensorStateName(0)) == "UNSUPPORTED_LEGACY_WIRE");
    EXPECT_TRUE(std::string(ivi::sensorStateName(3)) == "ERROR_NO_LAST_GOOD");
    EXPECT_TRUE(std::string(ivi::sensorStateName(4)) == "ERROR_USING_LAST_GOOD");
    EXPECT_TRUE(std::string(ivi::sensorStateName(6)) ==
                "RECOVERING_USING_LAST_GOOD");
    EXPECT_TRUE(std::string(ivi::sensorStateName(255)) == "UNSUPPORTED_CODE");
}

void run() {
    testStaleBoundaryAndLastGood();
    testFailSafeDoesNotRefreshBmsAge();
    testIdsAcknowledgementSequence();
    testSensorStateLabels();
}

}  // namespace

int main() {
    return runTestProgram("VehicleDataService P3 state and acknowledgement", run);
}
