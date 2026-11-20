#pragma once

#include "can_publisher.h"
#include "publisher.h"
#include "subscriber.h"

#include <functional>
#include <utility>

// In-process RTE-style routing, not an AUTOSAR runtime. send() invokes
// subscribers synchronously on the publishing thread, without a hidden queue.
class BmsMiddleware {
public:
    using DeliveryObserver = std::function<void(uint32_t, CanPublishResult)>;

    BmsMiddleware(CanDriver& driver, SecOcModule& secoc, bool secoc_enabled,
                  DeliveryObserver observer = {})
        : bridge_(driver, secoc, secoc_enabled), observer_(std::move(observer)) {
        connect();
    }

    BmsMiddleware(CanPublisher::AuthenticatedSender sender,DeliveryObserver observer={})
        :bridge_(std::move(sender)),observer_(std::move(observer)){
        connect();
    }

private:
    void connect(){
        subscribeBms(Subscriber<BmsStatusData>([this](const BmsStatusData& data) {
            report(0x100, bridge_.onBmsStatus(data));
        }));
        subscribeFailSafe(Subscriber<FailSafeEvent>([this](const FailSafeEvent& event) {
            report(0x101, bridge_.onFailSafeEvent(event));
        }));
    }

public:

    BmsMiddleware(const BmsMiddleware&) = delete;
    BmsMiddleware& operator=(const BmsMiddleware&) = delete;
    BmsMiddleware(BmsMiddleware&&) = delete;
    BmsMiddleware& operator=(BmsMiddleware&&) = delete;

    void publishBms(const BmsStatusData& data) { bms_.send(data); }
    void publishFailSafe(const FailSafeEvent& event) { failsafe_.send(event); }

    // Own the subscriber callback by value; no reference to a temporary adapter.
    void subscribeBms(Subscriber<BmsStatusData> subscriber) {
        bms_.subscribe([subscriber = std::move(subscriber)](const BmsStatusData& data) {
            subscriber.onReceive(data);
        });
    }
    void subscribeFailSafe(Subscriber<FailSafeEvent> subscriber) {
        failsafe_.subscribe([subscriber = std::move(subscriber)](const FailSafeEvent& event) {
            subscriber.onReceive(event);
        });
    }

private:
    void report(uint32_t id, CanPublishResult result) {
        if (observer_) observer_(id, result);
    }
    CanPublisher bridge_;
    DeliveryObserver observer_;
    Publisher<BmsStatusData> bms_;
    Publisher<FailSafeEvent> failsafe_;
};
