#include "physical_soh_tracker.h"
#include "physical_soc_ekf.h"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <unistd.h>

PhysicalSohTracker::PhysicalSohTracker(double initial,double nominal,std::uint64_t interval,
    std::string path,std::string configuration):percent_(initial),nominal_(nominal),max_interval_(interval),
    path_(std::move(path)),configuration_(std::move(configuration)){
    if(!std::isfinite(initial)||initial<0||initial>100||!std::isfinite(nominal)||nominal<=0||
       !interval||interval>60000||path_.empty()||configuration_.empty())throw std::invalid_argument("invalid SOH prior configuration");
    if(std::filesystem::exists(path_)){
        std::ifstream in(path_);std::string version,identity,extra;double capacity=0,value=0;std::uint64_t count=0;
        if(!(in>>version>>identity>>capacity>>value>>count)||in>>extra||version!="physical-soh-v1"||
           identity!=configuration_||capacity!=nominal_||!std::isfinite(value)||value<0||value>100)
            throw std::invalid_argument("SOH state invalid or incompatible; preserve it and choose a new state path");
        percent_=value;updates_=count;status_="restored";
    }
}
void PhysicalSohTracker::clearRest(){rest_count_=0;rest_at_=0;}
void PhysicalSohTracker::unavailable(){
    anchor_.reset();clearRest();last_seq_=last_at_=0;net_ah_=0;status_="held-gap";
}
void PhysicalSohTracker::save(){
    const auto temporary=path_+".tmp-"+std::to_string(::getpid());
    try{
        std::ofstream out(temporary,std::ios::trunc);
        out<<std::setprecision(17)<<"physical-soh-v1 "<<configuration_<<' '<<nominal_<<' '<<percent_<<' '<<updates_<<'\n';
        out.close();if(!out)throw std::runtime_error("SOH state write failed");
        std::filesystem::rename(temporary,path_);
    }catch(...){std::error_code ec;std::filesystem::remove(temporary,ec);throw;}
}
void PhysicalSohTracker::accept(std::uint64_t seq,std::uint64_t at,double v,double i,double t){
    const auto soc=PhysicalSocEkf::referenceSoc(v);
    if(!seq||!at||!soc||!std::isfinite(i)||!std::isfinite(t)||t<10||t>40){unavailable();return;}
    if(last_seq_&&seq==last_seq_)return;
    if(last_seq_&&(seq!=last_seq_+1||at<=last_at_||at-last_at_>max_interval_))unavailable();
    if(last_at_)net_ah_-=(last_current_+i)/2*double(at-last_at_)/3600000.;
    last_seq_=seq;last_at_=at;last_current_=i;
    // Charging invalidates this discharge-only interval; noise at rest does not.
    if(i>.020){anchor_.reset();clearRest();net_ah_=0;status_="held-charge";return;}
    if(std::abs(i)>.020){clearRest();status_=anchor_?"collecting-discharge":"waiting-start-rest";return;}
    if(!rest_count_||std::max(rest_max_,v)-std::min(rest_min_,v)>.010||std::abs(t-rest_temp_)>2){
        rest_at_=at;rest_min_=rest_max_=rest_mean_=v;rest_temp_=t;rest_count_=1;return;
    }
    rest_min_=std::min(rest_min_,v);rest_max_=std::max(rest_max_,v);
    rest_mean_+=(v-rest_mean_)/++rest_count_;
    if(at-rest_at_<1800000||rest_count_<3)return;
    const double resting_soc=*PhysicalSocEkf::referenceSoc(rest_mean_);
    if(!anchor_){anchor_=Anchor{resting_soc,net_ah_,rest_temp_};status_="start-rest-ready";clearRest();return;}
    const double used=net_ah_-anchor_->ah,delta=anchor_->soc-resting_soc;
    if(used<nominal_*.20||delta<.20){status_="held-insufficient-span";clearRest();return;}
    const double raw=used/delta/nominal_*100;
    if(std::abs(rest_temp_-anchor_->temperature)>2||!std::isfinite(raw)||raw<=0||raw>100){
        status_="held-invalid-candidate";
        std::cout<<"{\"result\":\"SOH_CANDIDATE_REJECTED\",\"candidate_percent\":"<<raw<<"}"<<std::endl;
        anchor_=Anchor{resting_soc,net_ah_,rest_temp_};clearRest();return;
    }
    // Conservative smoothing is a policy, not a calibrated confidence weight.
    const double old=percent_;percent_=.8*percent_+.2*raw;++updates_;
    try{save();status_="updated";}
    catch(const std::exception&){percent_=old;--updates_;status_="held-save-error";}
    std::cout<<"{\"result\":\"SOH_REFERENCE_UPDATE\",\"candidate_percent\":"<<raw
             <<",\"soh_percent\":"<<percent_<<",\"net_discharged_ah\":"<<used
             <<",\"rest_soc_delta\":"<<delta<<",\"status\":\""<<status_<<"\",\"physical_accuracy_verified\":false}"<<std::endl;
    anchor_=Anchor{resting_soc,net_ah_,rest_temp_};clearRest();
}
