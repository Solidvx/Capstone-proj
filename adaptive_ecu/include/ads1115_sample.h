#pragma once

#include "ads1115_conversion.h"
#include "ads1115_registers.h"
#include "adc_acquisition_gate.h"
#include <functional>

struct Ads1115Sample {
    std::int16_t raw = 0;
    float adc_v = 0;
    float pack_v = 0;
};

// Synchronous diagnostic acquisition only; never call in the product CAN loop.
// Caller serializes requests at >=100ms. The clock is monotonic milliseconds.
inline bool acquireAds1115Sample(Ads1115Registers& adc,
                                const std::function<std::uint64_t()>& now,
                                const std::function<void()>& wait_one_ms,
                                Ads1115Sample& output) {
    const auto start = now();
    const auto expired = [&] {
        const auto current = now();
        return current < start || current - start >= AdcAcquisitionGate::kAcceptanceWindowMs;
    };
    if (!adc.start()) return false;
    while (!expired()) {
        wait_one_ms();
        if (expired()) break;
        std::int16_t raw = 0;
        const auto result = adc.poll(raw);
        if (expired() || result == Ads1115Read::Error) break;
        if (result == Ads1115Read::Complete) {
            Ads1115Sample sample;
            sample.raw = raw;
            if (!convertAds1115Voltage(raw, sample.adc_v, sample.pack_v)) return false;
            output = sample;
            return true;
        }
    }
    adc.abandon();
    return false;
}
