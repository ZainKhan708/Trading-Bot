#pragma once

#include <string>

namespace trading_bot {

struct TradeRequest {
  std::string symbol;
  double quantity{};
};

[[nodiscard]] double compute_position_value(const TradeRequest& request, double last_price);

} // namespace trading_bot
