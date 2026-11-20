#pragma once

#include <cstddef>
#include <istream>
#include <string>

// The existing recovery input ceiling, now also applied to standalone CSV loads.
inline constexpr std::size_t kInputSourceMaxBytes = 16 * 1024 * 1024;

struct InputFingerprint {
    std::size_t bytes = 0;
    std::string sha256;
    std::string recovery_identity;
};

struct CapturedInput {
    std::string content;
    InputFingerprint fingerprint;
};

std::string inputSha256(const std::string& content);
// Parse this captured content, never re-open a file just to attest its bytes.
CapturedInput captureInput(std::istream& input, const std::string& recovery_prefix);
