#include "kucoin/token_bucket.hpp"

#include <algorithm>
#include <thread>

namespace kucoin {

TokenBucket::TokenBucket(double tokens_per_second, double max_tokens)
    : tokens_per_second_(tokens_per_second),
      max_tokens_(max_tokens),
      available_tokens_(max_tokens),
      last_refill_(std::chrono::steady_clock::now()) {}

void TokenBucket::refill() {
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration<double>(now - last_refill_).count();
    if (elapsed > 0) {
        available_tokens_ =
            std::min(max_tokens_, available_tokens_ + elapsed * tokens_per_second_);
        last_refill_ = now;
    }
}

void TokenBucket::acquire() {
    std::unique_lock<std::mutex> lock(mutex_);
    while (true) {
        refill();
        if (available_tokens_ >= 1.0) {
            available_tokens_ -= 1.0;
            return;
        }
        auto now = std::chrono::steady_clock::now();
        auto next_time = last_refill_ +
                         std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                             std::chrono::duration<double>(
                                 (1.0 - available_tokens_) / tokens_per_second_));
        if (next_time <= now) {
            next_time = now + std::chrono::milliseconds(10);
        }
        lock.unlock();
        std::this_thread::sleep_until(next_time);
        lock.lock();
    }
}

void TokenBucket::updateRate(double tokens_per_second, double max_tokens) {
    std::lock_guard<std::mutex> lock(mutex_);
    refill();
    tokens_per_second_ = tokens_per_second;
    max_tokens_ = max_tokens;
    available_tokens_ = std::min(available_tokens_, max_tokens_);
}

}  // namespace kucoin
