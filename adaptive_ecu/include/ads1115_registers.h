#pragma once
#include <cstddef>
#include <cstdint>

// Each operation must transfer exactly the requested bytes or return false.
// readRegister performs pointer-write followed by a two-byte read, MSB first.
class Ads1115Transport {
public:
    virtual ~Ads1115Transport() = default;
    virtual bool write(const std::uint8_t* bytes, std::size_t count) = 0;
    virtual bool readRegister(std::uint8_t pointer, std::uint8_t* bytes,
                              std::size_t count) = 0;
};

enum class Ads1115Read { Waiting, Complete, Error };

// Single-worker ownership. Timing and late-result rejection belong to the
// acquisition gate. This class does not open a device or change CAN framing.
class Ads1115Registers {
public:
    explicit Ads1115Registers(Ads1115Transport& transport) : transport_(transport) {}
    bool start();
    Ads1115Read poll(std::int16_t& raw);
    void abandon() { pending_ = false; }
private:
    bool readWord(std::uint8_t pointer, std::uint16_t& word);
    Ads1115Transport& transport_;
    bool pending_ = false;
};
