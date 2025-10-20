#pragma once

#include <string>
#include <unordered_map>

namespace kucoin {

struct KucoinCredentialsConfig {
    std::string api_key;
    std::string api_secret;
    std::string api_passphrase;
    std::string subaccount;
    bool paper{false};
};

class KucoinCredentials {
public:
    KucoinCredentials() = default;
    explicit KucoinCredentials(KucoinCredentialsConfig config);

    [[nodiscard]] const std::string& apiKey() const noexcept;
    [[nodiscard]] const std::string& apiSecret() const noexcept;
    [[nodiscard]] const std::string& apiPassphrase() const noexcept;
    [[nodiscard]] const std::string& subaccount() const noexcept;
    [[nodiscard]] bool paper() const noexcept;

    std::unordered_map<std::string, std::string> buildAuthHeaders(
        const std::string& method,
        const std::string& endpoint,
        const std::string& query_string,
        const std::string& body,
        const std::string& timestamp,
        bool sign_passphrase = true) const;

private:
    KucoinCredentialsConfig config_{};
};

}  // namespace kucoin
