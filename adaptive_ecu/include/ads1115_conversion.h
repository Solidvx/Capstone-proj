#pragma once

#include <cstdint>

// Nominal 0..3.3 V input is codes 0..26400 at PGA +/-4.096 V.
constexpr std::int16_t kAds1115NominalMaxCode = 26400;

// Endpoint tolerance (option B, 2026-10-03, CHG-011): codes within this many
// LSB (125 uV each, about 2 mV) outside 0..26400 are endpoint noise and read as
// the nearest endpoint. Measured design value, not a datasheet limit: 100 ECU
// RPi samples gave -4..6 at the 0 V end and 26342..26364 at the 3.3 V end.
// Re-evaluate after additional measurements.
constexpr std::int16_t kAds1115EndToleranceCodes = 16;

// No I2C or freshness check. Codes farther outside than the tolerance return
// false and leave outputs unchanged.
bool convertAds1115Voltage(std::int16_t raw, float& adc_voltage_v,
                          float& pack_voltage_v);
