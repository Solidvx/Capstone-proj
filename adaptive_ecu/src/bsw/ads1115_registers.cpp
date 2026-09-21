#include "ads1115_registers.h"

namespace {
// OS=1, AIN0/GND, +/-4.096V, single-shot, 128SPS, comparator disabled.
constexpr std::uint16_t kStartConfig = 0xC383;
}

bool Ads1115Registers::readWord(std::uint8_t pointer, std::uint16_t& word) {
    std::uint8_t bytes[2] = {};
    if (!transport_.readRegister(pointer, bytes, 2)) return false;
    word = static_cast<std::uint16_t>((static_cast<unsigned>(bytes[0]) << 8) | bytes[1]);
    return true;
}

bool Ads1115Registers::start() {
    if (pending_) return false;
    std::uint16_t config = 0;
    // Do not issue a start while a previous device conversion is still busy.
    if (!readWord(1, config) || (config & 0x8000) == 0) return false;
    const std::uint8_t command[] = {1, static_cast<std::uint8_t>(kStartConfig >> 8),
                                    static_cast<std::uint8_t>(kStartConfig & 0xff)};
    if (!transport_.write(command, 3)) return false;
    pending_ = true;
    return true;
}

Ads1115Read Ads1115Registers::poll(std::int16_t& raw) {
    if (!pending_) return Ads1115Read::Error;
    std::uint16_t config = 0;
    if (!readWord(1, config) || (config & 0x7fff) != (kStartConfig & 0x7fff)) {
        pending_ = false;
        return Ads1115Read::Error;
    }
    if ((config & 0x8000) == 0) return Ads1115Read::Waiting;
    std::uint16_t value = 0;
    pending_ = false;
    if (!readWord(0, value)) return Ads1115Read::Error;
    // Avoid implementation-defined unsigned-to-signed overflow conversion.
    const int signed_value = value >= 0x8000 ? static_cast<int>(value) - 65536 : value;
    raw = static_cast<std::int16_t>(signed_value);
    return Ads1115Read::Complete;
}
