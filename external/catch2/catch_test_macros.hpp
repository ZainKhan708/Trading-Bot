#pragma once

#include <exception>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace catch2 {

class TestFailure : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
};

class TestRegistry {
public:
  using TestFunc = void (*)();
  struct TestCase {
    std::string name;
    TestFunc func;
  };

  static TestRegistry& instance() {
    static TestRegistry registry;
    return registry;
  }

  void add(TestFunc func, std::string name) { tests_.push_back({std::move(name), func}); }

  int run_all() {
    std::size_t failures = 0;
    for (const auto& test : tests_) {
      try {
        test.func();
        std::cout << "[  PASSED  ] " << test.name << '\n';
      } catch (const TestFailure& ex) {
        ++failures;
        std::cout << "[  FAILED  ] " << test.name << " - " << ex.what() << '\n';
      } catch (const std::exception& ex) {
        ++failures;
        std::cout << "[  FAILED  ] " << test.name << " - unexpected exception: " << ex.what()
                  << '\n';
      } catch (...) {
        ++failures;
        std::cout << "[  FAILED  ] " << test.name << " - unknown exception" << '\n';
      }
    }

    std::cout << "[==========] " << tests_.size() << " test(s) executed" << '\n';
    if (failures == 0U) {
      std::cout << "[  PASSED  ] All tests passed" << '\n';
      return 0;
    }

    std::cout << "[  FAILED  ] " << failures << " test(s) failed" << '\n';
    return 1;
  }

private:
  std::vector<TestCase> tests_;
};

class AutoReg {
public:
  AutoReg(TestRegistry::TestFunc func, std::string name) {
    TestRegistry::instance().add(func, std::move(name));
  }
};

inline int run_all() {
  return TestRegistry::instance().run_all();
}

} // namespace catch2

#define CATCH_INTERNAL_TEST_NAME2(line) catch2_test_##line
#define CATCH_INTERNAL_TEST_NAME(line) CATCH_INTERNAL_TEST_NAME2(line)
#define CATCH_INTERNAL_AUTOREG_NAME2(line) catch2_autoreg_##line
#define CATCH_INTERNAL_AUTOREG_NAME(line) CATCH_INTERNAL_AUTOREG_NAME2(line)

#define TEST_CASE(name, tags)                                                                      \
  static void CATCH_INTERNAL_TEST_NAME(__LINE__)();                                                \
  static const ::catch2::AutoReg CATCH_INTERNAL_AUTOREG_NAME(__LINE__)(                            \
      &CATCH_INTERNAL_TEST_NAME(__LINE__), name);                                                  \
  static void CATCH_INTERNAL_TEST_NAME(__LINE__)()

#define REQUIRE(expr)                                                                              \
  do {                                                                                             \
    if (!(expr)) {                                                                                 \
      throw ::catch2::TestFailure(std::string{"Requirement failed: "} + #expr);                    \
    }                                                                                              \
  } while (false)

#define REQUIRE_THROWS_AS(expr, exception_type)                                                    \
  do {                                                                                             \
    bool caught_exception = false;                                                                 \
    try {                                                                                          \
      static_cast<void>(expr);                                                                     \
    } catch (const exception_type&) {                                                              \
      caught_exception = true;                                                                     \
    } catch (...) {                                                                                \
      throw ::catch2::TestFailure(std::string{"Unexpected exception type when expecting "} +       \
                                  #exception_type);                                                \
    }                                                                                              \
    if (!caught_exception) {                                                                       \
      throw ::catch2::TestFailure(std::string{"Expected exception: "} + #exception_type);          \
    }                                                                                              \
  } while (false)

#define Catch ::catch2
