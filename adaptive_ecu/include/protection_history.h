#pragma once

#include "failsafe_sm.h"
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <vector>

// Owner-thread state only. Cryptographic session keys/counters never enter it.
class ProtectionHistory {
public:
    using Id = std::array<std::uint8_t,16>;
    using IdSource = std::function<Id()>;
    struct Snapshot {
        unsigned version=1;
        Id lineage{},incident{};
        std::uint8_t state=0,reason=0,phase=0;
        std::uint32_t revision=0;
    };
    ProtectionHistory(IdSource source,const FailSafeStateMachine::Snapshot& current,
                      const std::optional<Snapshot>& restored=std::nullopt);
    static bool valid(const Snapshot& snapshot);
    static bool matches(const Snapshot& snapshot,const FailSafeStateMachine::Snapshot& current);
    // Failure isolates continuity metadata, never changes the battery FSM.
    bool observe(const FailSafeStateMachine::Snapshot& current);
    std::optional<Snapshot> snapshot()const;
    std::optional<std::vector<std::uint8_t>> body(const Id& instance)const;
    bool resumed()const{return resumed_;}
    bool failed()const{return failed_;}
private:
    Id nextId(const Id& previous);
    IdSource source_;
    Snapshot state_;
    bool synchronized_=false,resumed_=false,failed_=false;
};
