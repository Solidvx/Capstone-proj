#pragma once

#include "can_driver.h"
#include "can_tx_trace.h"

#include <atomic>
#include <mutex>
#include <memory>
#include <string>
#include <thread>

class SocketCanCdd : public CanDriver {
public:
    SocketCanCdd() = default;
    ~SocketCanCdd() override;

    bool open(const std::string& interface_name) override;
    void close() override;
    bool send(const CanFrame& frame) override;
    void registerCallback(CanCallback callback) override;
    void startReceive() override;
    void stopReceive() override;

    // Concrete driver lifecycle; CanDriver/HAL wire contract is unchanged.
    struct ReceiveHealth {
        bool stopped;
        bool faulted;
        std::uint64_t progress;
        std::uint64_t frames;
        int error;
    };
    ReceiveHealth receiveHealth() const;
    void requestReceiveStop();
    bool reapReceiveIfStopped();
    // Internal descriptor instrumentation only; configure before send/receive.
    void enableTxTrace(int fd,const std::array<std::uint8_t,16>& instance);

private:
    void receiveLoop();

    int socket_fd_ = -1;
    std::atomic<bool> running_{false};
    std::atomic<bool> stopped_{true}, faulted_{false};
    std::atomic<std::uint64_t> progress_{0}, frames_{0};
    std::atomic<int> receive_error_{0};
    std::thread receive_thread_;
    std::mutex callback_mutex_;
    CanCallback callback_;
    std::unique_ptr<CanTxTrace> tx_trace_;
};
