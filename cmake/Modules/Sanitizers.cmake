include_guard(GLOBAL)

function(trading_bot_apply_sanitizers)
  set(options)
  set(oneValueArgs)
  set(multiValueArgs TARGETS)
  cmake_parse_arguments(SANIT "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

  if(NOT SANIT_TARGETS)
    message(FATAL_ERROR "trading_bot_apply_sanitizers requires TARGETS")
  endif()

  foreach(target IN LISTS SANIT_TARGETS)
    if(NOT TARGET ${target})
      message(FATAL_ERROR "Unknown target '${target}'")
    endif()

    if(TRADING_BOT_ENABLE_ASAN)
      target_compile_options(${target} PRIVATE -fsanitize=address)
      target_link_options(${target} PRIVATE -fsanitize=address)
    endif()

    if(TRADING_BOT_ENABLE_UBSAN)
      target_compile_options(${target} PRIVATE -fsanitize=undefined)
      target_link_options(${target} PRIVATE -fsanitize=undefined)
    endif()

    if(TRADING_BOT_ENABLE_COVERAGE)
      target_compile_options(${target} PRIVATE --coverage -O0 -g)
      target_link_options(${target} PRIVATE --coverage)
    endif()
  endforeach()
endfunction()
