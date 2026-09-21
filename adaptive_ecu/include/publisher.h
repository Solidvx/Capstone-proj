#pragma once

#include <cstddef>
#include <functional>
#include <mutex>
#include <utility>
#include <vector>

template <typename T>
class Publisher {
public:
    using Callback = std::function<void(const T&)>;

    void subscribe(Callback callback) {
        std::lock_guard<std::mutex> lock(mutex_);
        subscribers_.push_back(std::move(callback));
    }

    void send(const T& data) const {
        std::vector<Callback> snapshot;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            snapshot = subscribers_;
        }

        for (const auto& callback : snapshot) {
            if (callback) {
                callback(data);
            }
        }
    }

    std::size_t subscriberCount() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return subscribers_.size();
    }

private:
    mutable std::mutex mutex_;
    std::vector<Callback> subscribers_;
};
