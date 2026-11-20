// Test-only executable: production runMain with a failing calculation dependency.
// No product CLI/environment fault switch is installed.
#include "bms_calculation_task.h"
#include <stdexcept>
#include <iostream>
#include <thread>
#include <chrono>
#ifdef ECU_TASK_RECOVER_FIXTURE
#include <cstdio>
#include <sys/syscall.h>
#include <unistd.h>
namespace {
void report(const char* phase,const BmsCalculation& work){
    const auto now=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    std::fprintf(stderr,"{\"result\":\"TEST_BMS_WORK\",\"phase\":\"%s\",\"generation\":%llu,\"sampled_ms\":%llu,\"monotonic_ms\":%lld,\"tid\":%ld}\n",
        phase,static_cast<unsigned long long>(work.generation),static_cast<unsigned long long>(work.sampled_at_ms),
        static_cast<long long>(now),::syscall(SYS_gettid));
}
}
#endif
int runMain(int,char**,BmsCalculationTask::Calculation);
int main(int argc,char** argv){
    unsigned calls=0;
    try{return runMain(argc,argv,[&](BmsCalculation& work){
#ifdef ECU_TASK_RECOVER_FIXTURE
        ++calls;
        if(calls==1)report("initial",work);
        if(calls==6){
            report("fault",work);
            std::this_thread::sleep_for(std::chrono::seconds(4));
            calculateBms(work);report("late-completed",work);
            return; // Owner already stopped this generation; result must be discarded.
        }
#else
        if(++calls>5){
#ifdef ECU_TASK_STALL_FIXTURE
            std::this_thread::sleep_for(std::chrono::seconds(6));
#else
            throw std::runtime_error("fixture calculation failed");
#endif
        }
#endif
        calculateBms(work);
#ifdef ECU_TASK_RECOVER_FIXTURE
        if(calls==7)report("completed",work);
#endif
    });}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
