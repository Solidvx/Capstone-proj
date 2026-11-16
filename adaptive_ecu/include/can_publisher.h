#pragma once

#include "bms_types.h"
#include "can_driver.h"
#include "secoc_module.h"

#include <mutex>
#include <functional>

CanFrame encodeBmsStatusFrame(const BmsStatusData& data);
CanFrame encodeFailSafeFrame(const FailSafeEvent& event);

enum class CanPublishResult { Sent, OriginalSendFailed, AuthenticationSendFailed, AwaitingSession };

// Synchronous subscriber bridge. The application owns the 100ms cadence;
// serialize each original/auth pair, including its per-stream counter issuance.
class CanPublisher {
public:
    CanPublisher(CanDriver& driver, SecOcModule& secoc, bool secoc_enabled);
    using AuthenticatedSender=std::function<CanPublishResult(const CanFrame&)>;
    explicit CanPublisher(AuthenticatedSender sender);
    CanPublishResult onBmsStatus(const BmsStatusData& data);
    CanPublishResult onFailSafeEvent(const FailSafeEvent& event);

private:
    CanPublishResult transmit(const CanFrame& original, uint32_t auth_id);
    CanDriver* driver_=nullptr;
    SecOcModule* secoc_=nullptr;
    const bool secoc_enabled_;
    std::mutex mutex_;
    AuthenticatedSender authenticated_sender_;
};
