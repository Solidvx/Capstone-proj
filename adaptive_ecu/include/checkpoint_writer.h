#pragma once

#include "recovery_checkpoint.h"
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>
#include <thread>

// One disk worker and at most one waiting snapshot. Submission never performs
// filesystem I/O. A newer waiting snapshot replaces an older waiting snapshot.
class CheckpointWriter {
public:
    using Store = std::function<void(const RecoveryCheckpoint&)>;
    struct Status {
        std::uint64_t requested=0, committed=0, failed=0;
        bool busy=false;
        bool storageFailed() const { return failed>committed; }
    };
    explicit CheckpointWriter(Store store);
    ~CheckpointWriter();
    CheckpointWriter(const CheckpointWriter&)=delete;
    CheckpointWriter& operator=(const CheckpointWriter&)=delete;
    std::uint64_t submit(RecoveryCheckpoint checkpoint);
    Status status() const;
private:
    void work();
    Store store_;
    mutable std::mutex mutex_;
    std::condition_variable wake_;
    std::optional<std::pair<std::uint64_t,RecoveryCheckpoint>> pending_;
    Status status_;
    bool stopping_=false;
    std::thread worker_;
};
