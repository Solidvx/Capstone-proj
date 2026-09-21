#include "can_publisher.h"

#include <algorithm>
#include <cmath>

namespace {
uint8_t encodePercent(float percent) {
    const int raw = static_cast<int>(std::lround(percent / 0.5f));
    return static_cast<uint8_t>(std::clamp(raw, 0, 200));
}

uint8_t encodeTemperature(int8_t temperature_c) {
    return static_cast<uint8_t>(std::clamp(static_cast<int>(temperature_c) + 40, 0, 165));
}
}

CanFrame encodeBmsStatusFrame(const BmsStatusData& data) {
    CanFrame frame{};
    frame.id = 0x100;
    frame.dlc = 8;

    const auto voltage_raw = static_cast<uint16_t>(
        std::clamp(static_cast<int>(std::lround(data.voltage_v / 0.01f)), 0, 65535));
    const auto current_raw = static_cast<int16_t>(
        std::clamp(static_cast<int>(std::lround(data.current_a / 0.1f)), -32768, 32767));
    const auto current_wire = static_cast<uint16_t>(current_raw);

    frame.data[0] = encodePercent(data.soc_percent);
    frame.data[1] = encodePercent(data.soh_percent);
    frame.data[2] = static_cast<uint8_t>((voltage_raw >> 8) & 0xFF);
    frame.data[3] = static_cast<uint8_t>(voltage_raw & 0xFF);
    frame.data[4] = static_cast<uint8_t>((current_wire >> 8) & 0xFF);
    frame.data[5] = static_cast<uint8_t>(current_wire & 0xFF);
    frame.data[6] = encodeTemperature(data.temperature_c);
    frame.data[7] = 0x00;

    return frame;
}

CanFrame encodeFailSafeFrame(const FailSafeEvent& event) {
    CanFrame frame{};
    frame.id = 0x101;
    frame.dlc = 8;
    frame.data[0] = event.prev_state;
    frame.data[1] = event.new_state;
    frame.data[2] = event.reason;
    frame.data[3] = encodePercent(event.soc_percent);
    frame.data[4] = encodeTemperature(event.temperature_c);
    frame.data[5] = 0x00;
    frame.data[6] = 0x00;
    frame.data[7] = 0x00;
    return frame;
}
