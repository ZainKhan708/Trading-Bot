#include "kucoin/credentials.hpp"

#include <stdexcept>

#include "kucoin/signer.hpp"

namespace kucoin {

KucoinCredentials::KucoinCredentials(KucoinCredentialsConfig config)
    : config_(std::move(config)) {
    if (config_.api_key.empty() || config_.api_secret.empty() ||
        config_.api_passphrase.empty()) {
        throw std::invalid_argument(
            "KucoinCredentials requires api_key, api_secret, and api_passphrase");
    }
}

const std::string& KucoinCredentials::apiKey() const noexcept {
    return config_.api_key;
}

const std::string& KucoinCredentials::apiSecret() const noexcept {
    return config_.api_secret;
}

const std::string& KucoinCredentials::apiPassphrase() const noexcept {
    return config_.api_passphrase;
}

const std::string& KucoinCredentials::subaccount() const noexcept {
    return config_.subaccount;
}

bool KucoinCredentials::paper() const noexcept { return config_.paper; }

std::unordered_map<std::string, std::string> KucoinCredentials::buildAuthHeaders(
    const std::string& method,
    const std::string& endpoint,
    const std::string& query_string,
    const std::string& body,
    const std::string& timestamp,
    bool sign_passphrase) const {
    KucoinSigner signer;
    std::unordered_map<std::string, std::string> headers;
    headers["KC-API-KEY"] = config_.api_key;
    headers["KC-API-TIMESTAMP"] = timestamp;
    headers["KC-API-KEY-VERSION"] = "2";

    std::string signature = signer.signForHeadersV2(config_.api_secret, timestamp,
                                                    method, endpoint, query_string,
                                                    body);
    headers["KC-API-SIGN"] = signature;

    if (!config_.subaccount.empty()) {
        headers["KC-API-PARTNER"] = config_.subaccount;
    }

    if (sign_passphrase) {
        headers["KC-API-PASSPHRASE"] =
            signer.signPassphrase(config_.api_secret, config_.api_passphrase);
    } else {
        headers["KC-API-PASSPHRASE"] = config_.api_passphrase;
    }

    return headers;
}

}  // namespace kucoin
