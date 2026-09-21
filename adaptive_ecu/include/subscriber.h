#pragma once

#include <functional>
#include <utility>

template <typename T>
class Subscriber {
public:
    using Callback = std::function<void(const T&)>;

    explicit Subscriber(Callback callback) : callback_(std::move(callback)) {}

    void onReceive(const T& data) const {
        if (callback_) {
            callback_(data);
        }
    }

private:
    Callback callback_;
};
