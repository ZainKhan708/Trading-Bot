#pragma once

#include <chrono>
#include <condition_variable>
#include <mutex>

namespace kucoin {

class TokenBucket {
public:
    TokenBucket(double tokens_per_second, double max_tokens);

    TokenBucket(const TokenBucket&) = delete;
    TokenBucket& operator=(const TokenBucket&) = delete;
    TokenBucket(TokenBucket&&) = delete;
    TokenBucket& operator=(TokenBucket&&) = delete;

    void acquire();

    void updateRate(double tokens_per_second, double max_tokens);

private:
    void refill();

    double tokens_per_second_;
    double max_tokens_;
    double available_tokens_;
    std::chrono::steady_clock::time_point last_refill_;
    std::mutex mutex_;
};

}  // namespace kucoin
