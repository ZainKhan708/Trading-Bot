#pragma once

#include <boost/asio.hpp>
#include <boost/beast.hpp>

#include <atomic>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "kucoin/credentials.hpp"
#include "kucoin/rest_client.hpp"

namespace kucoin {

struct OrderUpdate {
    std::string order_id;
    std::string symbol;
    std::string side;
    std::string status;
    double size{0.0};
    double filled_size{0.0};
    double price{0.0};
};

struct FillUpdate {
    std::string trade_id;
    std::string order_id;
    std::string symbol;
    std::string side;
    double size{0.0};
    double price{0.0};
    double fee{0.0};
};

using OrderHandler = std::function<void(const OrderUpdate&)>;
using FillHandler = std::function<void(const FillUpdate&)>;

class PrivateWebSocketSession {
public:
    PrivateWebSocketSession(KucoinCredentials credentials,
                            RestClient rest_client,
                            boost::asio::io_context& io_context,
                            OrderHandler order_handler,
                            FillHandler fill_handler,
                            std::function<void()> heartbeat_handler = {});
    ~PrivateWebSocketSession();

    void connect();
    void disconnect();

private:
    void authenticate();
    void startRead();
    void handleMessage(const std::string& message);
    void scheduleHeartbeat();
    void sendPing();
    void reconnect();

    KucoinCredentials credentials_;
    RestClient rest_client_;
    boost::asio::io_context& io_context_;
    std::unique_ptr<boost::beast::websocket::stream<boost::asio::ip::tcp::socket>> ws_;
    boost::asio::ip::tcp::resolver resolver_;
    OrderHandler order_handler_;
    FillHandler fill_handler_;
    std::function<void()> heartbeat_handler_;
    std::string ws_token_;
    std::string ws_endpoint_;
    std::atomic<bool> connected_{false};
    std::atomic<bool> stop_{false};
    std::mutex ws_mutex_;
    std::thread reader_thread_;
    std::thread heartbeat_thread_;
    std::chrono::milliseconds heartbeat_interval_{15000};
};

}  // namespace kucoin
