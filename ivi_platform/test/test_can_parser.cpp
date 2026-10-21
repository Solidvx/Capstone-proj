#include "can_parser.h"
#include "test_support.h"

namespace {

void run() {
    const ivi::CanPayload bms{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    const auto status = ivi::parseBmsStatus(bms);
    EXPECT_TRUE(status.has_value());
    EXPECT_NEAR(status->soc_percent, 75.0, 0.001);
    EXPECT_NEAR(status->soh_percent, 95.0, 0.001);
    EXPECT_NEAR(status->voltage_v, 42.0, 0.001);
    EXPECT_NEAR(status->current_a, -2.0, 0.001);
    EXPECT_NEAR(status->temperature_c, 25.0, 0.001);

    const ivi::CanPayload signed_boundary{0x00, 0x00, 0x00, 0x00,
                                          0x80, 0x00, 0x00, 0x00};
    const auto boundary = ivi::parseBmsStatus(signed_boundary);
    EXPECT_TRUE(boundary.has_value());
    EXPECT_NEAR(boundary->current_a, -3276.8, 0.001);
    EXPECT_NEAR(boundary->temperature_c, -40.0, 0.001);

    auto invalid_bms = bms;
    invalid_bms[7] = 2;
    EXPECT_FALSE(ivi::parseBmsStatus(invalid_bms).has_value());

    const ivi::CanPayload fail_safe{0x00, 0x01, 0x01, 0x26, 0x46, 0, 0, 0};
    const auto event = ivi::parseFailSafeEvent(fail_safe);
    EXPECT_TRUE(event.has_value());
    EXPECT_EQ(event->new_state, 1U);
    EXPECT_EQ(event->reason, 1U);
    EXPECT_NEAR(event->soc_percent, 19.0, 0.001);
    EXPECT_NEAR(event->temperature_c, 30.0, 0.001);

    const ivi::CanPayload watchdog{0x00, 0x01, 0x07, 0x96, 0x41, 0, 0, 0};
    EXPECT_TRUE(ivi::parseFailSafeEvent(watchdog).has_value());
    EXPECT_EQ(std::string(ivi::failSafeReasonName(0x07)), "WATCHDOG_RESTART_FAILED");
    auto undefined_reason = watchdog;
    undefined_reason[2] = 0;
    EXPECT_FALSE(ivi::parseFailSafeEvent(undefined_reason).has_value());

    const ivi::CanPayload auth{0xD0, 0xDD, 0xFC, 0x05, 0, 0, 0, 42};
    const auto parsed_auth = ivi::parseSecOcAuth(auth);
    EXPECT_TRUE(parsed_auth.has_value());
    EXPECT_EQ(parsed_auth->rolling_counter, 42U);

    const ivi::CanPayload ids{0x04, 0x96, 0x01, 0x00, 0, 0, 0, 1};
    const auto alert = ivi::parseIdsAlert(ids);
    EXPECT_TRUE(alert.has_value());
    EXPECT_EQ(alert->attack_type, 4U);
    EXPECT_NEAR(alert->anomaly_score, 1.5, 0.001);
    EXPECT_EQ(alert->suspect_can_id, 0x0100U);
    EXPECT_EQ(alert->source_timestamp, 1U);

    const char* attack_names[] = {"None", "Fuzzy", "Replay", "Spoofing", "Flooding"};
    for (std::uint8_t code = 1; code <= 4; ++code) {
        auto vector = ids;
        vector[0] = code;
        const auto parsed = ivi::parseIdsAlert(vector);
        EXPECT_TRUE(parsed.has_value());
        EXPECT_EQ(parsed->attack_type, code);
        EXPECT_EQ(std::string(ivi::attackTypeName(parsed->attack_type)), attack_names[code]);
    }

    auto invalid_ids = ids;
    invalid_ids[0] = 5;
    EXPECT_FALSE(ivi::parseIdsAlert(invalid_ids).has_value());
    EXPECT_TRUE(ivi::isSupportedCanId(ivi::kCanIdBmsStatus));
    EXPECT_FALSE(ivi::isSupportedCanId(0x777));
}

}  // namespace

int main() {
    return runTestProgram("CAN parser ICD vectors", run);
}
