cmake_minimum_required(VERSION 3.16)
project(trading_bot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CURL REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(Boost REQUIRED COMPONENTS system thread json)

add_library(trading_bot
    src/kucoin/credentials.cpp
    src/kucoin/signer.cpp
    src/kucoin/token_bucket.cpp
    src/kucoin/rest_client.cpp
    src/kucoin/public_websocket.cpp
    src/kucoin/private_websocket.cpp
)

target_include_directories(trading_bot
    PUBLIC
        include
)

target_link_libraries(trading_bot
    PUBLIC
        CURL::libcurl
        OpenSSL::SSL
        OpenSSL::Crypto
        Boost::system
        Boost::thread
        Boost::json
)

add_executable(sample_app src/main.cpp)

target_link_libraries(sample_app PRIVATE trading_bot)
