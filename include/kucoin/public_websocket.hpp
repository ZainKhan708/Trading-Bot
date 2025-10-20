#pragma once

#include <boost/asio.hpp>
#include <boost/beast.hpp>

#include <atomic>
#include <functional>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <unordered_set>

namespace kucoin {

using MessageHandler = std::function<void(const std::string&)>;
using ErrorHandler = std::function<void(const boost::system::error_code&)>;

class PublicWebSocketFeed {
public:
    PublicWebSocketFeed(std::string url,
                        boost::asio::io_context& io_context,
                        MessageHandler on_message,
                        ErrorHandler on_error = {});
    ~PublicWebSocketFeed();

    void connect();
    void disconnect();
    void subscribe(const std::string& channel, const std::string& symbol);
    void unsubscribe(const std::string& channel, const std::string& symbol);

private:
    void startRead();
    void handleReconnect();
    void resubscribeAll();

    std::string url_;
    boost::asio::io_context& io_context_;
    std::unique_ptr<boost::beast::websocket::stream<boost::asio::ip::tcp::socket>> ws_;
    boost::asio::ip::tcp::resolver resolver_;
    MessageHandler on_message_;
    ErrorHandler on_error_;
    std::unordered_map<std::string, std::unordered_set<std::string>> subscriptions_;
    std::atomic<bool> connecting_{false};
    std::atomic<bool> connected_{false};
    std::mutex ws_mutex_;
    std::thread reader_thread_;
};

}  // namespace kucoin
