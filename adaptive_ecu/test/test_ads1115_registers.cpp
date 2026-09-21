#include "ads1115_registers.h"
#include <gtest/gtest.h>

namespace {
class FakeBus : public Ads1115Transport {
public:
    std::uint16_t config = 0x8583;
    bool fail = false;
    bool write(const std::uint8_t* b, std::size_t n) override {
        if (fail || n != 3 || b[0] != 1 || b[1] != 0xc3 || b[2] != 0x83) return false;
        config = 0x4383;
        return true;
    }
    bool readRegister(std::uint8_t p, std::uint8_t* b, std::size_t n) override {
        if (fail || n != 2) return false;
        const auto v = p == 1 ? config : 0xfffe;
        b[0] = static_cast<std::uint8_t>(v >> 8);
        b[1] = static_cast<std::uint8_t>(v & 255);
        return true;
    }
};
}
TEST(Ads1115Registers, WaitThenDecodeOneResult) {
    FakeBus bus; Ads1115Registers adc(bus); std::int16_t raw = 123;
    ASSERT_TRUE(adc.start());
    EXPECT_FALSE(adc.start());
    EXPECT_EQ(adc.poll(raw), Ads1115Read::Waiting);
    EXPECT_EQ(raw, 123);
    bus.config = 0xc383;
    EXPECT_EQ(adc.poll(raw), Ads1115Read::Complete);
    EXPECT_EQ(raw, -2);
    EXPECT_EQ(adc.poll(raw), Ads1115Read::Error);
}
TEST(Ads1115Registers, ReadFailurePreservesOutput) {
    FakeBus bus; Ads1115Registers adc(bus); std::int16_t raw = 123;
    ASSERT_TRUE(adc.start());
    bus.fail = true;
    EXPECT_EQ(adc.poll(raw), Ads1115Read::Error);
    EXPECT_EQ(raw, 123);
}
