#pragma once

#include "recovery_checkpoint.h"

#include <string>

// Integrity-checked local calculation snapshot, not a secret/key store or a
// cryptographically authenticated file. The service owns its private directory.
std::string encodeCheckpoint(const RecoveryCheckpoint& checkpoint);
RecoveryCheckpoint decodeCheckpoint(const std::string& bytes);
void saveCheckpointAtomic(const std::string& path, const RecoveryCheckpoint& checkpoint);
RecoveryCheckpoint loadCheckpoint(const std::string& path);
