#include <iostream>

#include "trading_bot/trading_bot.hpp"

int main() {
  trading_bot::TradeRequest request{.symbol = "DEMO", .quantity = 10.0};
  const double last_price = 12.5;
  std::cout << "Position value for " << request.symbol << ": "
            << trading_bot::compute_position_value(request, last_price) << '\n';
  return 0;
}
