include_guard(GLOBAL)

find_program(CLANG_FORMAT_EXE NAMES clang-format)

if(NOT CLANG_FORMAT_EXE)
  message(STATUS "clang-format not found: format target will be unavailable")
  return()
endif()

file(GLOB_RECURSE _format_sources
  CONFIGURE_DEPENDS
  ${CMAKE_CURRENT_SOURCE_DIR}/src/*.c*
  ${CMAKE_CURRENT_SOURCE_DIR}/include/*.h*
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/*.c*
)

add_custom_target(format
  COMMAND ${CLANG_FORMAT_EXE}
          -i
          ${_format_sources}
  COMMENT "Running clang-format on project sources"
)
