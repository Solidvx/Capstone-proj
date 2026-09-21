#include "ads1115_conversion.h"

#include <gtest/gtest.h>

TEST(Ads1115Conversion, NominalReferencePoints) {
    const int raw_values[] = {0, 13200, 26400};
    const float adc_expected[] = {0.0f, 1.65f, 3.3f};
    const float pack_expected[] = {30.0f, 36.0f, 42.0f};
    for (int i = 0; i < 3; ++i) {
        float adc = -1.0f, pack = -1.0f;
        ASSERT_TRUE(convertAds1115Voltage(static_cast<std::int16_t>(raw_values[i]), adc, pack));
        EXPECT_NEAR(adc, adc_expected[i], 1e-6f);
        EXPECT_NEAR(pack, pack_expected[i], 1e-5f);
    }
}

TEST(Ads1115Conversion, EverySignedCodeIsClassifiedWithoutClamping) {
    float previous = -1.0f;
    for (int raw = -32768; raw <= 32767; ++raw) {
        float adc = -123.0f, pack = -456.0f;
        const bool valid = convertAds1115Voltage(static_cast<std::int16_t>(raw), adc, pack);
        ASSERT_EQ(valid, raw >= 0 && raw <= 26400);
        if (!valid) {
            EXPECT_FLOAT_EQ(adc, -123.0f);
            EXPECT_FLOAT_EQ(pack, -456.0f);
        } else {
            EXPECT_GT(pack, previous);
            EXPECT_NEAR(adc, raw / 8000.0, 1e-6);
            EXPECT_NEAR(pack, 30.0 + raw / 2200.0, 1e-5);
            previous = pack;
        }
    }
}
