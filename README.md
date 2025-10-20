# Trading-Bot

A C++ scaffolding project focused on building KuCoin exchange connectivity. The codebase includes:

- API credential management with HMAC-SHA256 + Base64 signing for KuCoin header v2 authentication.
- A libcurl-powered REST client featuring configurable retries, exponential backoff, and token-bucket based endpoint throttling.
- Public and private WebSocket clients built on Boost.Beast with automatic reconnection, subscription replay, and lightweight event parsing for order and fill streams.

> ⚠️ **Security note:** never commit real API keys to the repository. Load secrets from environment variables or other secure storage before constructing `KucoinCredentials`.

## Requirements

- A C++20 capable compiler (GCC 11+, Clang 12+, or MSVC 19.30+)
- CMake 3.16+
- libcurl
- OpenSSL (for HMAC + Base64)
- Boost 1.75+ with the `system`, `thread`, and `json` components

## Building

```bash
cmake -S . -B build
cmake --build build
```

This produces the `trading_bot` static library and a `sample_app` executable that links against it.

## Next steps

- Wire real trading strategies to the REST/WebSocket surfaces.
- Provide TLS configuration for connecting to KuCoin's secure WebSocket endpoints.
- Integrate persistence, metrics, and richer error handling as production needs grow.
