#include "ads1115_conversion.h"

bool convertAds1115Voltage(std::int16_t raw, float& adc_voltage_v,
                          float& pack_voltage_v) {
    // Classify in integer space to avoid rejecting the nominal upper endpoint
    // due to floating-point rounding. This is not a sensor error tolerance.
    if (raw < 0 || raw > 26400) {
        return false;
    }
    const float adc = static_cast<float>(raw) * 4.096f / 32768.0f;
    const float pack = 30.0f + (adc / 3.3f) * 12.0f;
    adc_voltage_v = adc;
    pack_voltage_v = pack;
    return true;
}
