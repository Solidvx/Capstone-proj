#pragma once

#include <cstddef>

namespace ivi {

class ReceiveRetryBudget {
public:
    explicit ReceiveRetryBudget(std::size_t max_retries) : max_retries_(max_retries) {}

    bool consumeRetry() {
        if (retries_used_ >= max_retries_) {
            return false;
        }
        ++retries_used_;
        return true;
    }

    void reset() { retries_used_ = 0; }
    std::size_t retriesUsed() const { return retries_used_; }

private:
    std::size_t max_retries_ = 0;
    std::size_t retries_used_ = 0;
};

}  // namespace ivi
