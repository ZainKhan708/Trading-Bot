#pragma once

#include <openssl/hmac.h>
#include <string>
#include <string_view>
#include <vector>

namespace kucoin {

class KucoinSigner {
public:
    KucoinSigner() = default;

    [[nodiscard]] std::string signRaw(std::string_view secret,
                                      std::string_view payload) const;

    [[nodiscard]] std::string signForHeadersV2(std::string_view secret,
                                               std::string_view timestamp,
                                               std::string_view method,
                                               std::string_view endpoint,
                                               std::string_view query_string,
                                               std::string_view body) const;

    [[nodiscard]] std::string signPassphrase(std::string_view secret,
                                             std::string_view passphrase) const;
};

}  // namespace kucoin
