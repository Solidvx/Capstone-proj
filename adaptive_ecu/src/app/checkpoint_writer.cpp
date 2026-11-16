#include "checkpoint_writer.h"
#include <limits>
#include <stdexcept>
#include <utility>

CheckpointWriter::CheckpointWriter(Store store):store_(std::move(store)){
    if(!store_)throw std::invalid_argument("checkpoint writer requires store");
    worker_=std::thread([this]{work();});
}
CheckpointWriter::~CheckpointWriter(){
    {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}
    wake_.notify_one();
    worker_.join(); // process supervisor bounds overall termination if disk stalls
}
std::uint64_t CheckpointWriter::submit(RecoveryCheckpoint checkpoint){
    std::lock_guard<std::mutex> lock(mutex_);
    if(stopping_ || status_.requested==std::numeric_limits<std::uint64_t>::max())
        throw std::runtime_error("checkpoint writer stopped or sequence exhausted");
    const auto sequence=++status_.requested;
    pending_=std::make_pair(sequence,std::move(checkpoint));
    wake_.notify_one();return sequence;
}
CheckpointWriter::Status CheckpointWriter::status()const{
    std::lock_guard<std::mutex> lock(mutex_);return status_;
}
void CheckpointWriter::work(){
    while(true){
        std::unique_lock<std::mutex> lock(mutex_);
        wake_.wait(lock,[&]{return stopping_ || pending_.has_value();});
        if(!pending_)return;
        auto item=std::move(*pending_);pending_.reset();status_.busy=true;
        lock.unlock();
        bool saved=false;
        try{store_(item.second);saved=true;}catch(...){/* published through status; never terminate the control loop */}
        lock.lock();
        if(saved)status_.committed=item.first;else status_.failed=item.first;
        status_.busy=false;
    }
}
