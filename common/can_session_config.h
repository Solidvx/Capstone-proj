#pragma once
#include "can_session_exchange.h"
#include <string>

namespace capstone::session_v2 {
// Complete explicit policy; no implicit operational timing defaults. Not a key
// file. Unknown/duplicate/missing values and unbounded counts are rejected.
ExchangeLimits loadExchangeLimits(const std::string& path);
}
