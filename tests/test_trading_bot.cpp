#include "trading_bot/trading_bot.hpp"

#include <catch2/catch_test_macros.hpp>

#include <stdexcept>

TEST_CASE("Position value multiplies quantity and price", "[compute_position_value]") {
  trading_bot::TradeRequest request{.symbol = "ABC", .quantity = 4.0};
  REQUIRE(trading_bot::compute_position_value(request, 2.5) == 10.0);
}

TEST_CASE("Negative price throws", "[compute_position_value]") {
  trading_bot::TradeRequest request{.symbol = "XYZ", .quantity = 1.0};
  REQUIRE_THROWS_AS(trading_bot::compute_position_value(request, -1.0), std::invalid_argument);
}
