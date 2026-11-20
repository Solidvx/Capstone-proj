#pragma once

#include "can_driver.h"

#include <array>
#include <atomic>
#include <cstdint>

// Internal, opt-in trace. Does not change CanDriver or CAN wire contracts.
// The owner ignores SIGPIPE before enabling and transfers a private nonblocking
// pipe write descriptor. Each record is <=512 bytes, one write, never retried.
class CanTxTrace {
public:
    struct Attempt { std::uint64_t sequence, started_ns; };
    CanTxTrace(int fd, const std::array<std::uint8_t,16>& instance);
    static void validateFd(int fd);
    ~CanTxTrace();
    CanTxTrace(const CanTxTrace&) = delete;
    CanTxTrace& operator=(const CanTxTrace&) = delete;
    Attempt begin() noexcept;
    void complete(Attempt attempt, const CanFrame& frame, bool syscall_attempted,
                  std::int64_t returned_bytes, int error_number, bool accepted) noexcept;
    std::uint64_t dropped() const noexcept { return dropped_.load(); }
private:
    bool emit(const char* bytes, int length) noexcept;
    int fd_;
    std::array<char,33> instance_{};
    std::atomic<std::uint64_t> attempts_{0}, written_{0}, dropped_{0};
};
