#include "kucoin/rest_client.hpp"

#include <sstream>
#include <stdexcept>
#include <thread>

namespace kucoin {
namespace {

std::string mapToQuery(const std::map<std::string, std::string>& query) {
    if (query.empty()) {
        return "";
    }
    std::ostringstream oss;
    bool first = true;
    for (const auto& [key, value] : query) {
        if (!first) {
            oss << '&';
        }
        first = false;
        char* encoded_key = curl_easy_escape(nullptr, key.c_str(),
                                             static_cast<int>(key.size()));
        char* encoded_value = curl_easy_escape(nullptr, value.c_str(),
                                               static_cast<int>(value.size()));
        if (!encoded_key || !encoded_value) {
            if (encoded_key) {
                curl_free(encoded_key);
            }
            if (encoded_value) {
                curl_free(encoded_value);
            }
            continue;
        }
        oss << encoded_key << '=' << encoded_value;
        curl_free(encoded_key);
        curl_free(encoded_value);
    }
    return oss.str();
}

}  // namespace

RestClient::RestClient(RestClientConfig config)
    : config_(std::move(config)), curl_(curl_easy_init()) {
    if (!curl_) {
        throw std::runtime_error("Failed to initialize CURL");
    }
    curl_easy_setopt(curl_, CURLOPT_USERAGENT, "TradingBot/1.0");
}

RestClient::~RestClient() {
    if (curl_) {
        curl_easy_cleanup(curl_);
    }
}

RestClient::RestClient(RestClient&& other) noexcept
    : config_(std::move(other.config_)), curl_(other.curl_) {
    other.curl_ = nullptr;
}

RestClient& RestClient::operator=(RestClient&& other) noexcept {
    if (this != &other) {
        if (curl_) {
            curl_easy_cleanup(curl_);
        }
        config_ = std::move(other.config_);
        curl_ = other.curl_;
        other.curl_ = nullptr;
    }
    return *this;
}

size_t RestClient::writeBody(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* body = static_cast<std::string*>(userdata);
    body->append(ptr, size * nmemb);
    return size * nmemb;
}

size_t RestClient::writeHeader(char* buffer, size_t size, size_t nitems, void* userdata) {
    auto* headers =
        static_cast<std::map<std::string, std::string>*>(userdata);
    std::string header_line(buffer, size * nitems);
    auto pos = header_line.find(':');
    if (pos != std::string::npos) {
        std::string key = header_line.substr(0, pos);
        std::string value = header_line.substr(pos + 1);
        while (!value.empty() && (value.front() == ' ' || value.front() == '\t')) {
            value.erase(value.begin());
        }
        while (!value.empty() && (value.back() == '\r' || value.back() == '\n')) {
            value.pop_back();
        }
        (*headers)[key] = value;
    }
    return size * nitems;
}

std::string RestClient::buildUrl(
    const std::string& path,
    const std::map<std::string, std::string>& query) const {
    std::string url = config_.base_url + path;
    auto query_string = mapToQuery(query);
    if (!query_string.empty()) {
        url.append("?");
        url.append(query_string);
    }
    return url;
}

void RestClient::acquireToken(const std::string& endpoint) {
    auto it = config_.endpoint_limiters.find(endpoint);
    if (it != config_.endpoint_limiters.end() && it->second) {
        it->second->acquire();
    }
}

RestResponse RestClient::request(
    const std::string& method,
    const std::string& path,
    const std::map<std::string, std::string>& headers,
    std::string body,
    const std::map<std::string, std::string>& query) {
    if (!curl_) {
        throw std::runtime_error("CURL handle not initialized");
    }

    RestResponse response;

    std::string url = buildUrl(path, query);
    acquireToken(path);

    struct curl_slist* header_list = nullptr;
    for (const auto& [key, value] : headers) {
        std::string header_line = key + ": " + value;
        header_list = curl_slist_append(header_list, header_line.c_str());
    }

    curl_easy_setopt(curl_, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl_, CURLOPT_CUSTOMREQUEST, method.c_str());
    curl_easy_setopt(curl_, CURLOPT_HTTPHEADER, header_list);
    curl_easy_setopt(curl_, CURLOPT_TIMEOUT_MS, config_.request_timeout.count());
    curl_easy_setopt(curl_, CURLOPT_WRITEFUNCTION, &RestClient::writeBody);
    curl_easy_setopt(curl_, CURLOPT_WRITEDATA, &response.body);
    curl_easy_setopt(curl_, CURLOPT_HEADERFUNCTION, &RestClient::writeHeader);
    curl_easy_setopt(curl_, CURLOPT_HEADERDATA, &response.headers);

    if (method == "POST" || method == "PUT" || method == "PATCH") {
        curl_easy_setopt(curl_, CURLOPT_POSTFIELDS, body.c_str());
        curl_easy_setopt(curl_, CURLOPT_POSTFIELDSIZE, body.size());
    } else {
        curl_easy_setopt(curl_, CURLOPT_POSTFIELDS, nullptr);
        curl_easy_setopt(curl_, CURLOPT_POSTFIELDSIZE, 0);
    }

    RetryPolicy retry = config_.retry_policy;
    std::chrono::milliseconds delay = retry.initial_delay;

    CURLcode code = CURLE_OK;
    for (std::size_t attempt = 0; attempt < retry.max_attempts; ++attempt) {
        response.body.clear();
        response.headers.clear();
        code = curl_easy_perform(curl_);
        if (code == CURLE_OK) {
            break;
        }
        std::this_thread::sleep_for(delay);
        delay = std::chrono::milliseconds(static_cast<long>(
            static_cast<double>(delay.count()) * retry.backoff_multiplier));
    }

    curl_easy_getinfo(curl_, CURLINFO_RESPONSE_CODE, &response.status_code);

    if (header_list) {
        curl_slist_free_all(header_list);
    }

    if (code != CURLE_OK) {
        std::ostringstream oss;
        oss << "REST request failed for " << method << ' ' << url << ": "
            << curl_easy_strerror(code);
        throw std::runtime_error(oss.str());
    }

    return response;
}

void RestClient::setLimiter(const std::string& endpoint,
                            std::shared_ptr<TokenBucket> limiter) {
    config_.endpoint_limiters[endpoint] = std::move(limiter);
}

}  // namespace kucoin
