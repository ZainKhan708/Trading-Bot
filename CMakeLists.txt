cmake_minimum_required(VERSION 3.21)

project(TradingBot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(TRADING_BOT_ENABLE_WARNINGS "Enable project warnings" ON)
option(TRADING_BOT_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(TRADING_BOT_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(TRADING_BOT_ENABLE_COVERAGE "Enable coverage flags" OFF)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
endif()

include(cmake/Modules/Sanitizers.cmake)

add_library(trading_bot STATIC
    src/trading_bot.cpp
)

target_include_directories(trading_bot PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

if(TRADING_BOT_ENABLE_WARNINGS)
  include(cmake/Modules/Warnings.cmake)
  target_link_libraries(trading_bot PRIVATE trading_bot_warnings)
endif()

add_executable(trading_bot_app src/main.cpp)
target_link_libraries(trading_bot_app PRIVATE trading_bot)

include(CTest)

if(BUILD_TESTING)
  add_executable(trading_bot_tests
    tests/test_main.cpp
    tests/test_trading_bot.cpp
  )
  target_link_libraries(trading_bot_tests PRIVATE trading_bot)
  target_include_directories(trading_bot_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/external)
  add_test(NAME trading_bot_tests COMMAND trading_bot_tests)
endif()

set(_trading_bot_targets trading_bot trading_bot_app)
if(TARGET trading_bot_tests)
  list(APPEND _trading_bot_targets trading_bot_tests)
endif()
trading_bot_apply_sanitizers(TARGETS ${_trading_bot_targets})

include(cmake/Modules/Format.cmake)
