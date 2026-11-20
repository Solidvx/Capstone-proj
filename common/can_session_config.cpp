#include "can_session_config.h"
#include <fstream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>

namespace capstone::session_v2 {
ExchangeLimits loadExchangeLimits(const std::string& path){
    std::ifstream input(path,std::ios::binary);
    if(!input)throw std::invalid_argument("cannot open explicit session policy");
    std::string contents;char byte;
    while(input.get(byte)){
        contents.push_back(byte);
        if(contents.size()>4096)throw std::invalid_argument("session policy exceeds4096bytes");
    }
    if(!input.eof())throw std::invalid_argument("session policy read failed");
    std::map<std::string,std::uint64_t> values;
    std::istringstream lines(contents);std::string line;
    while(std::getline(lines,line)){
        const auto comment=line.find('#');if(comment!=std::string::npos)line.resize(comment);
        for(auto& c:line)if(c=='=')c=' ';
        std::istringstream fields(line);std::string key,number,extra;
        if(!(fields>>key))continue;
        if(!(fields>>number)||fields>>extra||number.empty()||number.find_first_not_of("0123456789")!=std::string::npos)
            throw std::invalid_argument("session policy expects key=unsigned_integer");
        std::uint64_t value;
        try{value=std::stoull(number);}catch(...){throw std::invalid_argument("session policy integer overflow");}
        if(!value||!values.emplace(key,value).second)throw std::invalid_argument("session policy zero or duplicate");
    }
    auto time=[&](const char* name){
        const auto it=values.find(name);if(it==values.end())throw std::invalid_argument("missing session policy value");
        const auto value=it->second;values.erase(it);
        if(value>86400000)throw std::invalid_argument("session timing exceeds24hours");return value;
    };
    auto count=[&](const char* name,unsigned maximum){const auto n=time(name);
        if(n>maximum)throw std::invalid_argument("session resource limit exceeded");return static_cast<unsigned>(n);};
    ExchangeLimits out{};
    out.retry_ms=time("retry_ms");out.phase_ms=time("phase_ms");out.total_ms=time("total_ms");
    out.assembly_ms=time("assembly_ms");out.cache_ms=time("cache_ms");out.backoff_ms=time("backoff_ms");
    out.max_batches=count("max_batches",1024);out.max_verifications=count("max_verifications",65536);
    out.receive.pair_ms=time("receive_pair_ms");out.receive.order_ms=time("receive_order_ms");
    out.receive.budget_window_ms=time("receive_budget_window_ms");
    out.receive.candidates_per_stream=count("receive_candidates",16);out.receive.general_slots=count("receive_general_slots",64);
    out.receive.protected_slots=count("receive_protected_slots",32);out.receive.max_mac_checks=count("receive_max_mac_checks",65536);
    out.diagnostic.assembly_ms=time("diagnostic_assembly_ms");out.diagnostic.verification_window_ms=time("diagnostic_window_ms");
    out.diagnostic.assemblies=count("diagnostic_assemblies",8);out.diagnostic.max_verifications=count("diagnostic_max_verifications",65536);
    if(!values.empty())throw std::invalid_argument("unknown session policy field");
    validateReceiveLimits(out.receive);validateDiagnosticLimits(out.diagnostic);
    if(out.retry_ms>out.phase_ms||out.phase_ms>out.total_ms||out.assembly_ms>out.phase_ms||
       out.receive.pair_ms>out.phase_ms||out.receive.order_ms>=out.phase_ms)
        throw std::invalid_argument("inconsistent session policy timing");
    return out;
}
}
