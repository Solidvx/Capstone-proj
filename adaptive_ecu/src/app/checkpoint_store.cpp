#include "checkpoint_store.h"

#include <openssl/sha.h>
#include <cmath>
#include <charconv>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {
constexpr std::size_t kMaxBytes = 65536;
const std::string kHeader = "CAPSTONE-CHECKPOINT-V1\n";

std::string idHex(const ProtectionHistory::Id& id){
    std::ostringstream out;out<<std::hex<<std::setfill('0');
    for(auto byte:id)out<<std::setw(2)<<static_cast<unsigned>(byte);
    return out.str();
}
ProtectionHistory::Id parseId(const std::string& text){
    if(text.size()!=32 || text.find_first_not_of("0123456789abcdef")!=std::string::npos)
        throw std::invalid_argument("checkpoint protection identifier syntax");
    ProtectionHistory::Id result{};
    for(unsigned i=0;i<16;++i)result[i]=static_cast<std::uint8_t>(std::stoul(text.substr(2*i,2),nullptr,16));
    return result;
}

bool identityValid(const std::string& id) {
    if (id.empty() || id.size() > 128) return false;
    for (unsigned char c : id)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_' || c == ':')) return false;
    return true;
}

void validate(const RecoveryCheckpoint& cp) {
    EkfSocEstimator::Config config;
    config.capacity_ah = cp.ekf.capacity_ah;
    config.process_noise = cp.ekf.process_noise;
    config.measurement_noise = cp.ekf.measurement_noise;
    EkfSocEstimator ekf(config);
    SohEstimator soh(cp.soh.initial_capacity_ah);
    FailSafeStateMachine fsm;
    const auto& s = cp.sensor;
    const auto& walk = s.random_walk_state;
    const bool mode_valid = s.mode == SensorSimulator::Mode::CONSTANT ||
        s.mode == SensorSimulator::Mode::PROFILE_CSV || s.mode == SensorSimulator::Mode::RANDOM_WALK ||
        s.mode == SensorSimulator::Mode::ADS1115_HARDWARE;
    const bool index_valid = s.mode == SensorSimulator::Mode::PROFILE_CSV ?
        s.profile_size > 0 && s.profile_index < s.profile_size : s.profile_size == 0 && s.profile_index == 0;
    if (!validCheckpointProtection(cp) || !identityValid(cp.input_identity) || !identityValid(cp.soh_identity) ||
        !std::isfinite(cp.soh_elapsed_s) || cp.soh_elapsed_s < 0 ||
        !ekf.restoreState(cp.ekf) || !soh.restoreState(cp.soh) || !fsm.restoreState(cp.failsafe) ||
        s.version != 1 || !mode_valid || !index_valid ||
        !std::isfinite(walk.voltage_v) || walk.voltage_v < 30 || walk.voltage_v > 42 ||
        !std::isfinite(walk.current_a) || walk.current_a < -10 || walk.current_a > 5 ||
        walk.temperature_c < -10 || walk.temperature_c > 70)
        throw std::invalid_argument("invalid or incomplete recovery checkpoint");
}

std::string digest(const std::string& body) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    if (!SHA256(reinterpret_cast<const unsigned char*>(body.data()), body.size(), hash))
        throw std::runtime_error("checkpoint digest failed");
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (auto byte : hash) out << std::setw(2) << static_cast<unsigned>(byte);
    return out.str();
}
}

std::string encodeCheckpoint(const RecoveryCheckpoint& cp) {
    validate(cp);
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out << std::setprecision(std::numeric_limits<double>::max_digits10);
    out << cp.version << '\n';
    out << cp.ekf.version << ' ' << cp.ekf.soc << ' ' << cp.ekf.covariance << ' '
        << cp.ekf.capacity_ah << ' ' << cp.ekf.process_noise << ' ' << cp.ekf.measurement_noise << '\n';
    out << cp.soh.version << ' ' << cp.soh.initial_capacity_ah << ' ' << cp.soh.estimated_capacity_ah
        << ' ' << cp.soh.accumulated_discharge_ah << '\n';
    out << cp.failsafe.version << ' ' << static_cast<unsigned>(cp.failsafe.state) << ' '
        << static_cast<unsigned>(cp.failsafe.reason);
    if(cp.failsafe.version==2)out << ' ' << cp.failsafe.critical_latched;
    out << '\n';
    out << cp.sensor.version << ' ' << static_cast<unsigned>(cp.sensor.mode) << ' '
        << cp.sensor.profile_index << ' ' << cp.sensor.profile_size << ' '
        << cp.sensor.random_walk_state.voltage_v << ' ' << cp.sensor.random_walk_state.current_a << ' '
        << static_cast<int>(cp.sensor.random_walk_state.temperature_c) << '\n';
    out << cp.soh_elapsed_s << '\n' << std::quoted(cp.input_identity) << ' ' << std::quoted(cp.soh_identity)
        << '\n' << cp.sensor.rng << '\n';
    if(cp.version==2){
        out<<"protection "<<static_cast<unsigned>(cp.protection.has_value())<<'\n';
        if(cp.protection){
            const auto& p=*cp.protection;
            out<<p.version<<' '<<idHex(p.lineage)<<' '<<idHex(p.incident)<<' '
               <<static_cast<unsigned>(p.state)<<' '<<static_cast<unsigned>(p.reason)<<' '
               <<static_cast<unsigned>(p.phase)<<' '<<p.revision<<'\n';
        }
    }
    const auto body = out.str();
    const auto result = kHeader + digest(body) + '\n' + body;
    if (result.size() > kMaxBytes) throw std::invalid_argument("checkpoint size limit");
    return result;
}

RecoveryCheckpoint decodeCheckpoint(const std::string& bytes) {
    if (bytes.size() > kMaxBytes || bytes.compare(0, kHeader.size(), kHeader) != 0)
        throw std::invalid_argument("checkpoint header or size");
    const auto hash_end = bytes.find('\n', kHeader.size());
    if (hash_end != kHeader.size() + 64) throw std::invalid_argument("checkpoint digest format");
    const auto body = bytes.substr(hash_end + 1);
    if (digest(body) != bytes.substr(kHeader.size(), 64)) throw std::invalid_argument("checkpoint corruption");
    RecoveryCheckpoint cp;
    unsigned state = 0, reason = 0, mode = 0;
    int temp = 0;
    std::istringstream in(body);
    in.imbue(std::locale::classic());
    in >> cp.version >> cp.ekf.version >> cp.ekf.soc >> cp.ekf.covariance >> cp.ekf.capacity_ah
       >> cp.ekf.process_noise >> cp.ekf.measurement_noise
       >> cp.soh.version >> cp.soh.initial_capacity_ah >> cp.soh.estimated_capacity_ah >> cp.soh.accumulated_discharge_ah
       >> cp.failsafe.version >> state >> reason;
    if(cp.failsafe.version==2)in >> cp.failsafe.critical_latched;
    in >> cp.sensor.version >> mode >> cp.sensor.profile_index >> cp.sensor.profile_size
       >> cp.sensor.random_walk_state.voltage_v >> cp.sensor.random_walk_state.current_a >> temp
       >> cp.soh_elapsed_s >> std::quoted(cp.input_identity) >> std::quoted(cp.soh_identity) >> cp.sensor.rng;
    if (!in || state > 3 || reason > 7 || mode > 3 || temp < -10 || temp > 70)
        throw std::invalid_argument("checkpoint syntax or enum range");
    if(cp.version==2){
        std::string marker;unsigned present=2;
        in>>marker>>present;
        if(!in || marker!="protection" || present>1)
            throw std::invalid_argument("checkpoint protection marker");
        if(present){
            ProtectionHistory::Snapshot p;std::string lineage,incident,revision;
            unsigned risk=256,why=256,phase=256;
            in>>p.version>>lineage>>incident>>risk>>why>>phase>>revision;
            if(!in || risk>3 || why>7 || phase>2)
                throw std::invalid_argument("checkpoint protection syntax");
            const auto parsed=std::from_chars(revision.data(),revision.data()+revision.size(),p.revision);
            if(parsed.ec!=std::errc{} || parsed.ptr!=revision.data()+revision.size())
                throw std::invalid_argument("checkpoint protection revision syntax");
            p.lineage=parseId(lineage);p.incident=parseId(incident);
            p.state=static_cast<std::uint8_t>(risk);p.reason=static_cast<std::uint8_t>(why);
            p.phase=static_cast<std::uint8_t>(phase);cp.protection=p;
        }
    }
    in >> std::ws;
    if (!in.eof()) throw std::invalid_argument("checkpoint trailing data");
    cp.failsafe.state = static_cast<FailSafeStateMachine::State>(state);
    cp.failsafe.reason = static_cast<FailSafeStateMachine::Reason>(reason);
    cp.sensor.mode = static_cast<SensorSimulator::Mode>(mode);
    cp.sensor.random_walk_state.temperature_c = static_cast<int8_t>(temp);
    validate(cp);
    return cp;
}

void saveCheckpointAtomic(const std::string& path, const RecoveryCheckpoint& cp) {
    const auto bytes = encodeCheckpoint(cp); // refuse invalid replacement before opening a file
#if defined(__unix__) || defined(__APPLE__)
    const std::filesystem::path destination(path);
    const auto directory = destination.has_parent_path() ? destination.parent_path() : std::filesystem::path(".");
    std::string pattern = path + ".tmp.XXXXXX";
    std::vector<char> name(pattern.begin(), pattern.end()); name.push_back('\0');
    int fd = ::mkstemp(name.data());
    if (fd < 0) throw std::runtime_error("checkpoint temporary file creation failed");
    bool renamed = false;
    try {
        if (::fchmod(fd, 0600) != 0 || ::fcntl(fd, F_SETFD, FD_CLOEXEC) != 0)
            throw std::runtime_error("checkpoint file permissions failed");
        std::size_t offset = 0;
        while (offset < bytes.size()) {
            const auto count = ::write(fd, bytes.data() + offset, bytes.size() - offset);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) throw std::runtime_error("checkpoint write failed");
            offset += static_cast<std::size_t>(count);
        }
        if (::fsync(fd) != 0) throw std::runtime_error("checkpoint file sync failed");
        const int closing = fd; fd = -1;
        if (::close(closing) != 0) throw std::runtime_error("checkpoint close failed");
        if (::rename(name.data(), path.c_str()) != 0) throw std::runtime_error("checkpoint replace failed");
        renamed = true;
        const int dir = ::open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (dir < 0) throw std::runtime_error("checkpoint directory open failed after replacement");
        const int synced = ::fsync(dir); ::close(dir);
        if (synced != 0) throw std::runtime_error("checkpoint directory sync failed after replacement");
    } catch (...) {
        if (fd >= 0) ::close(fd);
        if (!renamed) ::unlink(name.data());
        throw;
    }
#else
    (void)path;
    throw std::runtime_error("checkpoint persistence requires POSIX");
#endif
}

RecoveryCheckpoint loadCheckpoint(const std::string& path) {
#if defined(__unix__) || defined(__APPLE__)
    const int fd = ::open(path.c_str(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) throw std::runtime_error("checkpoint open failed");
    std::string bytes;
    try {
        struct stat info{};
        if (::fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_uid != ::geteuid() ||
            (info.st_mode & 0077) != 0 || info.st_size < 0 || static_cast<std::uint64_t>(info.st_size) > kMaxBytes)
            throw std::runtime_error("checkpoint ownership, permissions or size rejected");
        char buffer[4096];
        while (true) {
            const auto count = ::read(fd, buffer, sizeof buffer);
            if (count < 0 && errno == EINTR) continue;
            if (count < 0) throw std::runtime_error("checkpoint read failed");
            if (count == 0) break;
            bytes.append(buffer, static_cast<std::size_t>(count));
            if (bytes.size() > kMaxBytes) throw std::runtime_error("checkpoint size limit");
        }
    } catch (...) { ::close(fd); throw; }
    ::close(fd);
    return decodeCheckpoint(bytes);
#else
    (void)path;
    throw std::runtime_error("checkpoint persistence requires POSIX");
#endif
}
