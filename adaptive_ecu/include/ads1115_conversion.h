#pragma once

#include <cstdint>

// Nominal 0..3.3 V input, PGA +/-4.096 V. No I2C or freshness check.
// Returns false outside the nominal range and leaves outputs unchanged.
bool convertAds1115Voltage(std::int16_t raw, float& adc_voltage_v,
                          float& pack_voltage_v);
