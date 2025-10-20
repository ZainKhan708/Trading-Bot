#include "trading_bot/trading_bot.hpp"

#include <stdexcept>

namespace trading_bot {

double compute_position_value(const TradeRequest& request, double last_price) {
  if (last_price < 0.0) {
    throw std::invalid_argument{"Last price cannot be negative"};
  }
  return request.quantity * last_price;
}

} // namespace trading_bot
