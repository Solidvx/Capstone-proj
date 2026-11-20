#include "input_lineage.h"
#include "input_source.h"
#include "ads1115_conversion.h"
#include "hardware_sample_feed.h"
#include "linux_i2c_transport.h"

#include <openssl/sha.h>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <locale>
#include <sstream>
#include <stdexcept>

std::string inputSha256(const std::string& content) {
    unsigned char digest[SHA256_DIGEST_LENGTH];
    if (!SHA256(reinterpret_cast<const unsigned char*>(content.data()),content.size(),digest))
        throw std::runtime_error("input fingerprint failed");
    std::ostringstream out;
    out<<std::hex<<std::setfill('0');
    for (auto byte:digest) out<<std::setw(2)<<static_cast<unsigned>(byte);
    return out.str();
}

CapturedInput captureInput(std::istream& input,const std::string& recovery_prefix) {
    CapturedInput captured;
    char chunk[4096];
    while (input.read(chunk,sizeof chunk) || input.gcount()) {
        const auto count=static_cast<std::size_t>(input.gcount());
        if (count>kInputSourceMaxBytes-captured.content.size())
            throw std::runtime_error("input source exceeds existing16MiB recovery bound");
        captured.content.append(chunk,count);
    }
    if (!input.eof() || input.bad()) throw std::runtime_error("input source read failed");
    captured.fingerprint={captured.content.size(),inputSha256(captured.content),
        inputSha256(recovery_prefix+captured.content)};
    return captured;
}

namespace {
void fingerprint(std::ostream& out,const std::optional<InputFingerprint>& input) {
    if (!input) {out<<"null";return;}
    out<<"{\"bytes\":"<<input->bytes<<",\"sha256\":\""<<input->sha256<<"\"}";
}
}

std::string inputLineageJson(const std::string& instance,const std::string& intent,
    SensorSimulator::Mode mode,const SensorSimulator& sensor,
    const SensorSimulator::Snapshot& state,const SohCapacityScenario& soh,double elapsed,
    const std::string& i2c_binding) {
    if (instance.size()!=32 || !std::all_of(instance.begin(),instance.end(),[](char c){
            return (c>='0' && c<='9') || (c>='a' && c<='f');}) ||
        instance[12]!='4' || (instance[16]!='8' && instance[16]!='9' && instance[16]!='a' && instance[16]!='b') ||
        (intent!="standalone" && intent!="fresh" && intent!="resume") || state.mode!=mode ||
        !std::isfinite(elapsed) || elapsed<0)
        throw std::invalid_argument("invalid input lineage instance/intent/state");
    const char* name=nullptr;
    switch (mode) {
    case SensorSimulator::Mode::CONSTANT:name="constant";break;
    case SensorSimulator::Mode::PROFILE_CSV:name="profile_csv";break;
    case SensorSimulator::Mode::RANDOM_WALK:name="random_walk";break;
    case SensorSimulator::Mode::ADS1115_HARDWARE:name="ads1115";break;
    }
    if (!name || (mode==SensorSimulator::Mode::PROFILE_CSV && !sensor.profileInput()))
        throw std::invalid_argument("input lineage requires a loaded source");
    if (mode==SensorSimulator::Mode::ADS1115_HARDWARE && (i2c_binding.size()!=64 ||
        !std::all_of(i2c_binding.begin(),i2c_binding.end(),[](char c){
            return (c>='0' && c<='9') || (c>='a' && c<='f');})))
        throw std::invalid_argument("input lineage requires an ADC device binding fingerprint");
    if (mode==SensorSimulator::Mode::RANDOM_WALK &&
        (!std::isfinite(state.random_walk_state.voltage_v) || !std::isfinite(state.random_walk_state.current_a)))
        throw std::invalid_argument("input lineage requires a finite walk state");
    std::ostringstream out;
    out.imbue(std::locale::classic());out<<std::setprecision(17);
    out<<"{\"result\":\"ECU_INPUT_LINEAGE\",\"schema\":\"ecu-input-lineage-v1\","
       <<"\"instance_id\":\""<<instance<<"\",\"start_intent\":\""<<intent
       <<"\",\"configuration\":{\"source_mode\":\""<<name
       <<"\",\"ground_truth_label\":\"unattested\",\"calculation_dt_s\":0.1,"
       <<"\"sensor_units\":{\"voltage\":\"V\",\"current\":\"A\",\"temperature\":\"degC\"},"
       <<"\"voltage_semantics\":\"product_interprets_as_pack_voltage\",\"sensor\":{";
    if (mode==SensorSimulator::Mode::CONSTANT) {
        out<<"\"origin\":\"virtual_constant\",\"values\":[42,-2,25]";
    } else if (mode==SensorSimulator::Mode::PROFILE_CSV) {
        out<<"\"origin\":\"csv_values_not_physically_attested\",\"input\":";
        fingerprint(out,sensor.profileInput());
        out<<",\"rows\":"<<state.profile_size
           <<",\"columns\":[\"voltage\",\"current\",\"temperature\"],"
           <<"\"temperature_conversion\":\"round_half_away_from_zero_then_clamp\","
           <<"\"temperature_bounds_degC\":[-10,70],\"row_clock\":\"one_row_per_committed_sample\","
           <<"\"end_policy\":\"hold_last\",\"empty_policy\":\"nominal_constant_fallback\"";
    } else if (mode==SensorSimulator::Mode::RANDOM_WALK) {
        out<<"\"origin\":\"virtual_random_walk\",\"seed\":"<<SensorSimulator::kRandomSeed
           <<",\"engine\":\"std::mt19937\",\"distribution\":\"std::normal_distribution<float>\","
           <<"\"cross_library_bitwise_reproducible\":false,\"initial_values\":[42,-2,25],"
           <<"\"delta_stddev\":[0.08,0.25,0.20],\"bounds\":[[30,42],[-10,5],[-10,70]],"
           <<"\"temperature_conversion\":\"round_half_away_from_zero_then_clamp\"";
    } else {
        out<<"\"origin\":\"real_adc_with_virtual_pack_mapping\",\"channel\":0,\"i2c_address\":"
           <<static_cast<unsigned>(LinuxI2cTransport::kAds1115Address)
           <<",\"device_binding_sha256\":\""<<i2c_binding<<'"'
           <<",\"adc_lsb_v\":0.000125,\"nominal_adc_v\":[0,3.3],\"nominal_codes\":[0,"
           <<kAds1115NominalMaxCode<<"],\"endpoint_tolerance_codes\":"<<kAds1115EndToleranceCodes
           <<",\"endpoint_policy\":\"clamp_inside_tolerance_otherwise_reject\",\"virtual_pack_v\":[30,42],"
           <<"\"mapping\":\"pack_v=30+(clamped_code*4.096/32768)/3.3*12\","
           <<"\"virtual_current_a\":"<<SensorSimulator::kHardwareCurrentA
           <<",\"virtual_temperature_degC\":"<<static_cast<int>(SensorSimulator::kHardwareTemperatureC)
           <<",\"freshness_ms\":"<<HardwareSampleFeed::kFreshnessMs
           <<",\"startup_recovery_gate\":\"three_new_valid_conversions\"";
    }
    out<<"},\"soh\":{\"origin\":\"virtual_capacity_scenario\",\"initial_capacity_ah\":"
       <<kVirtualBatteryCapacityAh<<",\"input\":";
    fingerprint(out,soh.inputFingerprint());
    out<<",\"steps\":"<<soh.size()<<",\"units\":{\"elapsed\":\"s\",\"capacity\":\"Ah\"},"
       <<"\"step_policy\":\"previous_step_hold_last\",\"clock\":\"steady_elapsed_plus_restored_offset\"}},"
       <<"\"state\":{\"profile_index\":"<<state.profile_index<<",\"soh_elapsed_s\":"<<elapsed;
    if (mode==SensorSimulator::Mode::RANDOM_WALK) {
        std::ostringstream rng;rng.imbue(std::locale::classic());rng<<state.rng;
        out<<",\"rng_state_sha256\":\""<<inputSha256(rng.str())<<"\",\"walk_values\":["
           <<state.random_walk_state.voltage_v<<','<<state.random_walk_state.current_a<<','
           <<static_cast<int>(state.random_walk_state.temperature_c)<<']';
    }
    out<<"}}";
    return out.str();
}
