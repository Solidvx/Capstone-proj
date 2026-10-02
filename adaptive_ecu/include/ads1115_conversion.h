#pragma once

#include <cstdint>

// Nominal 0..3.3 V input is codes 0..26400 at PGA +/-4.096 V.
constexpr std::int16_t kAds1115NominalMaxCode = 26400;

// Endpoint tolerance (option B, CHG-011): codes within this many LSB (125 uV
// each, about 4 mV) outside 0..26400 are endpoint noise and read as the nearest
// endpoint. Measured design value, not a datasheet limit. ECU RPi at the 0 V
// end: 100 samples gave -4..6; a later 1000 samples gave -20..19 with 2 below
// -16, so the first value 16 was widened to 32 (about 1.6x the largest observed
// excursion). The 3.3 V end gave 26342..26364 in 100 samples.
// Re-evaluate after additional measurements.
constexpr std::int16_t kAds1115EndToleranceCodes = 32;

// No I2C or freshness check. Codes farther outside than the tolerance return
// false and leave outputs unchanged.
bool convertAds1115Voltage(std::int16_t raw, float& adc_voltage_v,
                          float& pack_voltage_v);
