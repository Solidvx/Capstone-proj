#include "ads1115_conversion.h"

#include <algorithm>

bool convertAds1115Voltage(std::int16_t raw, float& adc_voltage_v,
                          float& pack_voltage_v) {
    // Classify in integer space to avoid rejecting the nominal upper endpoint
    // due to floating-point rounding.
    const int code = raw;
    if (code < -kAds1115EndToleranceCodes ||
        code > kAds1115NominalMaxCode + kAds1115EndToleranceCodes) {
        return false;
    }
    // Only endpoint noise inside the tolerance is mapped to the endpoint.
    const int nominal = std::clamp(code, 0, static_cast<int>(kAds1115NominalMaxCode));
    const float adc = static_cast<float>(nominal) * 4.096f / 32768.0f;
    const float pack = 30.0f + (adc / 3.3f) * 12.0f;
    adc_voltage_v = adc;
    pack_voltage_v = pack;
    return true;
}
