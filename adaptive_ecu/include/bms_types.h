#pragma once

#include <cstdint>

struct BmsStatusData {
    float soc_percent = 75.0f;
    float soh_percent = 95.0f;
    float voltage_v = 42.0f;
    float current_a = -2.0f;
    int8_t temperature_c = 25;
};

struct FailSafeEvent {
    uint8_t prev_state = 0;
    uint8_t new_state = 0;
    uint8_t reason = 0;
    float soc_percent = 0.0f;
    int8_t temperature_c = 25;
};
