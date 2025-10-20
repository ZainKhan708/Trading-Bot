include_guard(GLOBAL)

add_library(trading_bot_warnings INTERFACE)

set(_warnings
  -Wall
  -Wextra
  -Wpedantic
  -Wconversion
  -Wshadow
  -Wnon-virtual-dtor
  -Wold-style-cast
  -Wcast-align
  -Wunused
  -Woverloaded-virtual
  -Wnull-dereference
  -Wdouble-promotion
  -Wformat=2
)

target_compile_options(trading_bot_warnings INTERFACE ${_warnings})
