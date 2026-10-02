#pragma once

#include <optional>

#include "can_types.h"

namespace ivi {

std::optional<BmsStatus> parseBmsStatus(const CanPayload& payload);
std::optional<FailSafeEvent> parseFailSafeEvent(const CanPayload& payload);
std::optional<SecOcAuth> parseSecOcAuth(const CanPayload& payload);
std::optional<SecurityAlert> parseIdsAlert(const CanPayload& payload);

bool isSupportedCanId(std::uint32_t can_id);
const char* failSafeStateName(std::uint8_t state);
const char* failSafeReasonName(std::uint8_t reason);
const char* sensorStateName(std::uint8_t state);
const char* attackTypeName(std::uint8_t attack_type);

}  // namespace ivi
