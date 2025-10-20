#include "kucoin/signer.hpp"

#include <openssl/buffer.h>
#include <openssl/evp.h>

#include <stdexcept>
#include <vector>

namespace kucoin {
namespace {

std::string base64Encode(const unsigned char* input, size_t length) {
    BIO* bmem = BIO_new(BIO_s_mem());
    BIO* b64 = BIO_new(BIO_f_base64());
    BIO_set_flags(b64, BIO_FLAGS_BASE64_NO_NL);
    b64 = BIO_push(b64, bmem);
    BIO_write(b64, input, static_cast<int>(length));
    BIO_flush(b64);
    BUF_MEM* bptr = nullptr;
    BIO_get_mem_ptr(b64, &bptr);
    std::string result(bptr->data, bptr->length);
    BIO_free_all(b64);
    return result;
}

}  // namespace

std::string KucoinSigner::signRaw(std::string_view secret,
                                  std::string_view payload) const {
    unsigned int len = 0;
    std::vector<unsigned char> hmac(EVP_MAX_MD_SIZE);
    HMAC(EVP_sha256(), secret.data(), static_cast<int>(secret.size()),
         reinterpret_cast<const unsigned char*>(payload.data()),
         payload.size(), hmac.data(), &len);
    return base64Encode(hmac.data(), len);
}

std::string KucoinSigner::signForHeadersV2(std::string_view secret,
                                           std::string_view timestamp,
                                           std::string_view method,
                                           std::string_view endpoint,
                                           std::string_view query_string,
                                           std::string_view body) const {
    std::string payload;
    payload.reserve(timestamp.size() + method.size() + endpoint.size() +
                    query_string.size() + body.size() + 4);
    payload.append(timestamp);
    payload.append(method);
    payload.append(endpoint);
    if (!query_string.empty()) {
        payload.push_back('?');
        payload.append(query_string);
    }
    if (!body.empty()) {
        payload.append(body);
    }
    return signRaw(secret, payload);
}

std::string KucoinSigner::signPassphrase(std::string_view secret,
                                         std::string_view passphrase) const {
    return signRaw(secret, passphrase);
}

}  // namespace kucoin
