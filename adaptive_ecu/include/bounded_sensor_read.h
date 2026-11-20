#pragma once

#include <cstdint>
#include <functional>
#include <string>

struct BoundedSensorRead {
    enum class Status { Complete, Timeout, Interrupted, ChildError, Unreclaimed };
    Status status;
    std::string text;
};
// Linux standalone capture boundary, not a worker inside the ECU process.
// At most one child, bounded reply, kill/reap before another device request.
BoundedSensorRead readSensorBounded(const std::function<std::string()>& read,
    unsigned timeout_ms, const std::function<bool()>& keep_running);
