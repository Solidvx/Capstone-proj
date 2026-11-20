#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string_view>

enum class Ds18b20Status { Complete, Malformed, CrcError, RetainedValue,
                          RangeError, AmbiguousPowerOn };
struct Ds18b20Result {
    Ds18b20Status status=Ds18b20Status::Malformed;
    std::array<std::uint8_t,9> scratchpad{};
    std::optional<double> temperature_c;
};
const char* ds18b20StatusName(Ds18b20Status status);
// Parse one fresh w1_slave read; reject NO CRC and mismatched retained data.
// No device discovery, cached fallback or fabricated 25C. Exact 85C remains
// explicitly ambiguous rather than pretending to prove a completed conversion.
Ds18b20Result parseDs18b20(std::string_view text);
