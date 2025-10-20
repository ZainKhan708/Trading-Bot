#pragma once

#include <curl/curl.h>

#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>

#include "kucoin/token_bucket.hpp"

namespace kucoin {

struct RestResponse {
    long status_code{0};
    std::string body;
    std::map<std::string, std::string> headers;
};

struct RetryPolicy {
    std::size_t max_attempts{5};
    std::chrono::milliseconds initial_delay{500};
    double backoff_multiplier{2.0};
};

class RestClientConfig {
public:
    std::string base_url{"https://api.kucoin.com"};
    RetryPolicy retry_policy{};
    std::chrono::milliseconds request_timeout{10000};
    std::unordered_map<std::string, std::shared_ptr<TokenBucket>> endpoint_limiters{};
};

class RestClient {
public:
    explicit RestClient(RestClientConfig config = {});
    ~RestClient();

    RestClient(const RestClient&) = delete;
    RestClient& operator=(const RestClient&) = delete;

    RestClient(RestClient&&) noexcept;
    RestClient& operator=(RestClient&&) noexcept;

    RestResponse request(const std::string& method,
                         const std::string& path,
                         const std::map<std::string, std::string>& headers,
                         std::string body = {},
                         const std::map<std::string, std::string>& query = {});

    void setLimiter(const std::string& endpoint, std::shared_ptr<TokenBucket> limiter);

private:
    static size_t writeBody(char* ptr, size_t size, size_t nmemb, void* userdata);
    static size_t writeHeader(char* buffer, size_t size, size_t nitems, void* userdata);

    std::string buildUrl(const std::string& path,
                         const std::map<std::string, std::string>& query) const;

    void acquireToken(const std::string& endpoint);

    RestClientConfig config_;
    CURL* curl_;
};

}  // namespace kucoin
