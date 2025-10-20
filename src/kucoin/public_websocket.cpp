#include "kucoin/public_websocket.hpp"

#include <boost/asio/connect.hpp>
#include <boost/beast/core/flat_buffer.hpp>
#include <boost/beast/websocket.hpp>

#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace kucoin {
namespace {

struct ParsedUrl {
    std::string host;
    std::string port;
    std::string target;
};

ParsedUrl parseUrl(const std::string& url) {
    constexpr std::string_view ws_prefix = "ws://";
    constexpr std::string_view wss_prefix = "wss://";
    std::string_view view(url);
    bool secure = false;
    if (view.rfind(ws_prefix, 0) == 0) {
        view.remove_prefix(ws_prefix.size());
    } else if (view.rfind(wss_prefix, 0) == 0) {
        view.remove_prefix(wss_prefix.size());
        secure = true;
    } else {
        throw std::invalid_argument("Unsupported websocket URL scheme");
    }
    if (secure) {
        throw std::invalid_argument("Secure websocket URLs require TLS configuration");
    }

    auto slash_pos = view.find('/');
    std::string host_port;
    std::string target = "/";
    if (slash_pos == std::string::npos) {
        host_port = std::string(view);
    } else {
        host_port = std::string(view.substr(0, slash_pos));
        target += std::string(view.substr(slash_pos + 1));
    }

    auto colon_pos = host_port.find(':');
    ParsedUrl result;
    if (colon_pos == std::string::npos) {
        result.host = host_port;
        result.port = "80";
    } else {
        result.host = host_port.substr(0, colon_pos);
        result.port = host_port.substr(colon_pos + 1);
    }
    result.target = target;
    return result;
}

std::string makeSubscriptionMessage(const std::string& channel,
                                    const std::string& symbol,
                                    bool subscribe) {
    std::string action = subscribe ? "subscribe" : "unsubscribe";
    std::string topic = channel + ":" + symbol;
    std::string message =
        std::string("{\"type\":\"") + action + "\",\"topic\":\"" + topic +
        "\",\"privateChannel\":false,\"response\":true}";
    return message;
}

}  // namespace

PublicWebSocketFeed::PublicWebSocketFeed(std::string url,
                                         boost::asio::io_context& io_context,
                                         MessageHandler on_message,
                                         ErrorHandler on_error)
    : url_(std::move(url)),
      io_context_(io_context),
      resolver_(io_context),
      on_message_(std::move(on_message)),
      on_error_(std::move(on_error)) {}

PublicWebSocketFeed::~PublicWebSocketFeed() {
    disconnect();
    if (reader_thread_.joinable()) {
        reader_thread_.join();
    }
}

void PublicWebSocketFeed::connect() {
    if (connecting_.exchange(true)) {
        return;
    }
    try {
        auto parsed = parseUrl(url_);
        auto results = resolver_.resolve(parsed.host, parsed.port);
        auto ws = std::make_unique<
            boost::beast::websocket::stream<boost::asio::ip::tcp::socket>>(io_context_);
        boost::asio::connect(ws->next_layer(), results.begin(), results.end());
        ws->handshake(parsed.host, parsed.target);

        {
            std::lock_guard<std::mutex> lock(ws_mutex_);
            ws_ = std::move(ws);
        }
        connected_ = true;
        connecting_ = false;
        resubscribeAll();
        startRead();
    } catch (const std::exception& ex) {
        connecting_ = false;
        if (on_error_) {
            on_error_(boost::system::errc::make_error_code(
                boost::system::errc::not_connected));
        }
        std::thread([this]() {
            std::this_thread::sleep_for(std::chrono::seconds(3));
            handleReconnect();
        }).detach();
        std::cerr << "Public websocket connect failed: " << ex.what() << std::endl;
    }
}

void PublicWebSocketFeed::disconnect() {
    connected_ = false;
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (ws_) {
        boost::system::error_code ec;
        ws_->close(boost::beast::websocket::close_code::normal, ec);
        ws_.reset();
    }
}

void PublicWebSocketFeed::subscribe(const std::string& channel,
                                    const std::string& symbol) {
    subscriptions_[channel].insert(symbol);
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (ws_ && connected_) {
        auto message = makeSubscriptionMessage(channel, symbol, true);
        ws_->write(boost::asio::buffer(message));
    }
}

void PublicWebSocketFeed::unsubscribe(const std::string& channel,
                                      const std::string& symbol) {
    auto channel_it = subscriptions_.find(channel);
    if (channel_it != subscriptions_.end()) {
        channel_it->second.erase(symbol);
        if (channel_it->second.empty()) {
            subscriptions_.erase(channel_it);
        }
    }
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (ws_ && connected_) {
        auto message = makeSubscriptionMessage(channel, symbol, false);
        ws_->write(boost::asio::buffer(message));
    }
}

void PublicWebSocketFeed::startRead() {
    if (reader_thread_.joinable()) {
        reader_thread_.join();
    }
    reader_thread_ = std::thread([this]() {
        boost::beast::flat_buffer buffer;
        while (connected_) {
            std::unique_lock<std::mutex> lock(ws_mutex_);
            if (!ws_) {
                lock.unlock();
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                continue;
            }
            boost::system::error_code ec;
            ws_->read(buffer, ec);
            lock.unlock();
            if (ec) {
                connected_ = false;
                if (on_error_) {
                    on_error_(ec);
                }
                handleReconnect();
                break;
            }
            auto data = buffer.data();
            std::string message(boost::asio::buffers_begin(data),
                                boost::asio::buffers_end(data));
            buffer.consume(buffer.size());
            if (on_message_) {
                on_message_(message);
            }
        }
    });
}

void PublicWebSocketFeed::handleReconnect() {
    if (connected_ || connecting_) {
        return;
    }
    std::thread([this]() {
        std::this_thread::sleep_for(std::chrono::seconds(2));
        connect();
    }).detach();
}

void PublicWebSocketFeed::resubscribeAll() {
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (!ws_) {
        return;
    }
    for (const auto& [channel, symbols] : subscriptions_) {
        for (const auto& symbol : symbols) {
            auto message = makeSubscriptionMessage(channel, symbol, true);
            ws_->write(boost::asio::buffer(message));
        }
    }
}

}  // namespace kucoin
