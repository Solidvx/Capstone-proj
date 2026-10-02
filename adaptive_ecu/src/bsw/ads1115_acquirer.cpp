#include "ads1115_acquirer.h"

#include "ads1115_conversion.h"

#include <chrono>
#include <utility>

Ads1115Acquirer::Ads1115Acquirer(Ads1115Transport& transport, Clock now)
    : adc_(transport), now_(std::move(now)) {}

bool Ads1115Acquirer::tick() {
    const auto now = now_();
    if (!gate_.pending()) {
        // The gate enforces the 100 ms request interval, including after failures.
        if (!gate_.begin(now)) return false;
        if (adc_.start()) return false;
        gate_.finish(now_(), false);
        recordError();
        return true;
    }
    if (gate_.expired(now)) {
        // No I2C call is outstanding here; tick() owns every transfer.
        adc_.abandon();
        gate_.finish(now, false);
        recordError();
        return true;
    }
    if (!gate_.pollDue(now)) return false;

    std::int16_t raw = 0;
    const auto result = adc_.poll(raw);
    if (result == Ads1115Read::Waiting) return false;

    float adc_v = 0.0f;
    float pack_v = 0.0f;
    const bool converted =
        result == Ads1115Read::Complete && convertAds1115Voltage(raw, adc_v, pack_v);
    // Judge lateness after the transfer has returned, not when it started.
    const auto done = now_();
    if (gate_.finish(done, converted)) {
        recordValid(done, raw, adc_v, pack_v);
    } else {
        recordError();
    }
    return true;
}

void Ads1115Acquirer::recordValid(std::uint64_t done_ms, std::int16_t raw, float adc_v,
                                  float pack_v) {
    ++snapshot_.sequence;
    snapshot_.last_valid_sequence = snapshot_.sequence;
    snapshot_.last_valid_ms = done_ms;
    snapshot_.raw = raw;
    snapshot_.adc_v = adc_v;
    snapshot_.pack_v = pack_v;
}

void Ads1115Acquirer::recordError() {
    ++snapshot_.sequence;
    snapshot_.last_error_sequence = snapshot_.sequence;
}

Ads1115AcquisitionWorker::Ads1115AcquisitionWorker(Ads1115Transport& transport,
                                                   Ads1115Acquirer::Clock now)
    : acquirer_(transport, std::move(now)) {}

Ads1115AcquisitionWorker::~Ads1115AcquisitionWorker() {
    stop();
}

void Ads1115AcquisitionWorker::start() {
    if (running_.exchange(true)) return;
    thread_ = std::thread(&Ads1115AcquisitionWorker::loop, this);
}

void Ads1115AcquisitionWorker::stop() {
    running_ = false;
    if (thread_.joinable()) thread_.join();
}

AdcSnapshot Ads1115AcquisitionWorker::snapshot() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return published_;
}

void Ads1115AcquisitionWorker::loop() {
    while (running_) {
        if (acquirer_.tick()) {
            const auto latest = acquirer_.snapshot();
            std::lock_guard<std::mutex> lock(mutex_);
            published_ = latest;
        }
        std::this_thread::sleep_for(
            std::chrono::milliseconds(AdcAcquisitionGate::kPollIntervalMs));
    }
}
