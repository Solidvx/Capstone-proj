#include "bms_calculation_task.h"

#include <cmath>
#include <stdexcept>
#include <system_error>
#include <utility>

void calculateBms(BmsCalculation& work) {
    if(!std::isfinite(work.capacity_ah) || work.capacity_ah<=0 ||
       work.capacity_ah>work.soh.initialCapacityAh())
        throw std::invalid_argument("invalid BMS capacity input");
    work.sample=work.sensor.next();
    // Missing time is never integrated as if it contained valid observations.
    work.soc_percent=work.ekf.update(.1f,work.sample.current_a,work.sample.voltage_v)*100.0f;
    work.soh.recordCycle(work.capacity_ah);
    work.soh_percent=work.soh.soh()*100.0f;
    if(!std::isfinite(work.soc_percent) || !std::isfinite(work.soh_percent))
        throw std::runtime_error("invalid BMS calculation result");
}

BmsCalculationTask::BmsCalculationTask(Calculation calculation)
    : calculation_(std::move(calculation)) {
    if(!calculation_)throw std::invalid_argument("BMS calculation callback required");
}
BmsCalculationTask::~BmsCalculationTask() {
    requestStop();
    // Only final owner teardown may wait. Recovery uses joinIfStopped and must
    // never replace an unreclaimed worker; external manual stop owns its bound.
    if(thread_.joinable())thread_.join();
}
void BmsCalculationTask::checkpointCommitted(std::uint64_t now_ms) {
    std::lock_guard<std::mutex> lock(mutex_);committed_at_=now_ms;
}
bool BmsCalculationTask::submit(BmsCalculation work) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(stopping_ || stopped_ || busy_ || pending_ || completed_)return false;
    work.generation=generation_;
    pending_=std::move(work);wake_.notify_one();return true;
}
std::optional<BmsCalculation> BmsCalculationTask::takeCompleted() {
    std::lock_guard<std::mutex> lock(mutex_);
    auto result=std::move(completed_);completed_.reset();return result;
}
bool BmsCalculationTask::faulted() const {
    std::lock_guard<std::mutex> lock(mutex_);return faulted_;
}
void BmsCalculationTask::requestStop() {
    std::lock_guard<std::mutex> lock(mutex_);
    stopping_=true;pending_.reset();completed_.reset();completed_generation_.reset();wake_.notify_one();
}
bool BmsCalculationTask::joinIfStopped() {
    {std::lock_guard<std::mutex> lock(mutex_);if(!stopped_)return false;}
    if(thread_.joinable())thread_.join();return true;
}
bool BmsCalculationTask::snapshotValid(std::uint64_t now_ms,std::uint64_t max_age_ms) {
    std::lock_guard<std::mutex> lock(mutex_);
    return committed_at_ && now_ms>=*committed_at_ && now_ms-*committed_at_<=max_age_ms;
}
bool BmsCalculationTask::startFromSnapshot(std::uint64_t generation) {
    std::lock_guard<std::mutex> lock(mutex_);
    if(!stopped_ || thread_.joinable())return false;
    generation_=generation;stopping_=false;stopped_=false;faulted_=false;
    pending_.reset();completed_.reset();completed_generation_.reset();
    try{thread_=std::thread(&BmsCalculationTask::loop,this);}
    catch(const std::system_error&){stopping_=true;stopped_=true;faulted_=true;return false;}
    return true;
}
bool BmsCalculationTask::completedWork(std::uint64_t generation) {
    std::lock_guard<std::mutex> lock(mutex_);
    return !stopping_ && completed_generation_ && *completed_generation_==generation;
}
void BmsCalculationTask::loop() {
    std::unique_lock<std::mutex> lock(mutex_);
    while(!stopping_){
        wake_.wait(lock,[&]{return stopping_ || pending_.has_value();});
        if(stopping_)break;
        auto work=std::move(*pending_);pending_.reset();busy_=true;
        lock.unlock();
        bool failed=false;
        try{calculation_(work);}catch(...){failed=true;}
        lock.lock();busy_=false;
        if(failed){faulted_=true;stopping_=true;break;}
        if(!stopping_ && work.generation==generation_){
            completed_generation_=generation_;completed_=std::move(work);
        }
    }
    stopped_=true;
}
