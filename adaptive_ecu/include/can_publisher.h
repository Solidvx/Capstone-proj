#pragma once

#include "bms_types.h"
#include "can_driver.h"

CanFrame encodeBmsStatusFrame(const BmsStatusData& data);
CanFrame encodeFailSafeFrame(const FailSafeEvent& event);
