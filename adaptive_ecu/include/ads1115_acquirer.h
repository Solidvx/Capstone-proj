#pragma once

#include "adc_acquisition_gate.h"
#include "ads1115_registers.h"

#include <atomic>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

// Why the most recent request was rejected. Diagnostic only; every cause is
// handled the same way (no new valid result).
enum class AdcError : std::uint8_t {
    None,
    StartFailed,  // I2C failure or device still busy when starting a request
    Timeout,      // conversion not complete within the acceptance window
    ReadFailed,   // I2C failure or unexpected config while polling
    OutOfRange,   // completed, but raw is outside the endpoint tolerance
    Late,         // valid result returned after the acceptance window
};

// State published after every finished conversion request, valid or rejected.
// Sequence numbers identify new results; equal voltages are never compared.
struct AdcSnapshot {
    std::uint64_t sequence = 0;             // finished requests so far
    std::uint64_t last_error_sequence = 0;  // most recent rejected request
    std::uint64_t last_valid_sequence = 0;  // most recent accepted request
    std::uint64_t last_valid_ms = 0;        // monotonic completion time of that result
    std::int16_t raw = 0;                   // fields below hold the latest valid result
    float adc_v = 0.0f;
    float pack_v = 0.0f;
    AdcError last_error = AdcError::None;   // cause of last_error_sequence
    std::int16_t last_error_raw = 0;        // OutOfRange only
    std::uint64_t last_error_elapsed_ms = 0;  // Late only: request start to return
};

// One-line cause for logs, e.g. "reason=range raw=-35".
std::string describeAdcError(const AdcSnapshot& snapshot);

// ADC-1/2=A single-shot acquisition driven by a monotonic millisecond clock.
// Exactly one worker calls tick(); I2C calls complete inside tick().
class Ads1115Acquirer {
public:
    using Clock = std::function<std::uint64_t()>;

    Ads1115Acquirer(Ads1115Transport& transport, Clock now);

    // Advances one step. Returns true when a request finished during this call.
    bool tick();
    AdcSnapshot snapshot() const { return snapshot_; }

private:
    void recordValid(std::uint64_t done_ms, std::int16_t raw, float adc_v, float pack_v);
    void recordError(AdcError cause, std::int16_t raw = 0, std::uint64_t elapsed_ms = 0);

    Ads1115Registers adc_;
    AdcAcquisitionGate gate_;
    Clock now_;
    AdcSnapshot snapshot_;
    std::uint64_t request_start_ms_ = 0;
};

// Runs Ads1115Acquirer on its own thread so conversion waits never block the
// 100 ms BMS/CAN loop or the watchdog kick.
class Ads1115AcquisitionWorker {
public:
    Ads1115AcquisitionWorker(Ads1115Transport& transport, Ads1115Acquirer::Clock now);
    ~Ads1115AcquisitionWorker();
    Ads1115AcquisitionWorker(const Ads1115AcquisitionWorker&) = delete;
    Ads1115AcquisitionWorker& operator=(const Ads1115AcquisitionWorker&) = delete;

    void start();
    void stop();
    AdcSnapshot snapshot() const;

private:
    void loop();

    Ads1115Acquirer acquirer_;
    mutable std::mutex mutex_;
    AdcSnapshot published_;
    std::atomic<bool> running_{false};
    std::thread thread_;
};
