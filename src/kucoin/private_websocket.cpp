#include "kucoin/private_websocket.hpp"

#include <boost/asio/buffer.hpp>
#include <boost/asio/connect.hpp>
#include <boost/beast/core/flat_buffer.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/json.hpp>

#include <chrono>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <string_view>

namespace kucoin {
namespace {

struct ParsedUrl {
    std::string host;
    std::string port;
    std::string target;
    bool secure{false};
};

ParsedUrl parseWebsocketUrl(const std::string& url) {
    constexpr std::string_view ws_prefix = "ws://";
    constexpr std::string_view wss_prefix = "wss://";
    std::string_view view(url);
    ParsedUrl parsed;
    if (view.rfind(ws_prefix, 0) == 0) {
        view.remove_prefix(ws_prefix.size());
    } else if (view.rfind(wss_prefix, 0) == 0) {
        view.remove_prefix(wss_prefix.size());
        parsed.secure = true;
    } else {
        throw std::invalid_argument("Unsupported websocket URL");
    }

    auto slash_pos = view.find('/');
    std::string host_port;
    if (slash_pos == std::string::npos) {
        host_port = std::string(view);
        parsed.target = "/";
    } else {
        host_port = std::string(view.substr(0, slash_pos));
        parsed.target = std::string(view.substr(slash_pos));
    }

    auto colon_pos = host_port.find(':');
    if (colon_pos == std::string::npos) {
        parsed.host = host_port;
        parsed.port = parsed.secure ? "443" : "80";
    } else {
        parsed.host = host_port.substr(0, colon_pos);
        parsed.port = host_port.substr(colon_pos + 1);
    }
    return parsed;
}

std::string generateConnectId() {
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<uint64_t> dist;
    std::ostringstream oss;
    oss << std::hex << dist(gen);
    return oss.str();
}

long toMillisecondsSinceEpoch() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

void parseOrderMessage(const boost::json::value& value, OrderHandler& handler) {
    if (!handler || !value.is_object()) {
        return;
    }
    const auto& obj = value.as_object();
    if (!obj.contains("data")) {
        return;
    }
    const auto& data = obj.at("data").as_object();
    OrderUpdate update;
    if (auto it = data.find("orderId"); it != data.end() && it->value().is_string()) {
        update.order_id = it->value().as_string().c_str();
    }
    if (auto it = data.find("symbol"); it != data.end() && it->value().is_string()) {
        update.symbol = it->value().as_string().c_str();
    }
    if (auto it = data.find("side"); it != data.end() && it->value().is_string()) {
        update.side = it->value().as_string().c_str();
    }
    if (auto it = data.find("status"); it != data.end() && it->value().is_string()) {
        update.status = it->value().as_string().c_str();
    }
    if (auto it = data.find("size"); it != data.end()) {
        update.size = boost::json::value_to<double>(it->value());
    }
    if (auto it = data.find("filledSize"); it != data.end()) {
        update.filled_size = boost::json::value_to<double>(it->value());
    }
    if (auto it = data.find("price"); it != data.end()) {
        update.price = boost::json::value_to<double>(it->value());
    }
    handler(update);
}

void parseFillMessage(const boost::json::value& value, FillHandler& handler) {
    if (!handler || !value.is_object()) {
        return;
    }
    const auto& obj = value.as_object();
    if (!obj.contains("data")) {
        return;
    }
    const auto& data = obj.at("data").as_object();
    FillUpdate update;
    if (auto it = data.find("tradeId"); it != data.end() && it->value().is_string()) {
        update.trade_id = it->value().as_string().c_str();
    }
    if (auto it = data.find("orderId"); it != data.end() && it->value().is_string()) {
        update.order_id = it->value().as_string().c_str();
    }
    if (auto it = data.find("symbol"); it != data.end() && it->value().is_string()) {
        update.symbol = it->value().as_string().c_str();
    }
    if (auto it = data.find("side"); it != data.end() && it->value().is_string()) {
        update.side = it->value().as_string().c_str();
    }
    if (auto it = data.find("size"); it != data.end()) {
        update.size = boost::json::value_to<double>(it->value());
    }
    if (auto it = data.find("price"); it != data.end()) {
        update.price = boost::json::value_to<double>(it->value());
    }
    if (auto it = data.find("fee"); it != data.end()) {
        update.fee = boost::json::value_to<double>(it->value());
    }
    handler(update);
}

}  // namespace

PrivateWebSocketSession::PrivateWebSocketSession(
    KucoinCredentials credentials,
    RestClient rest_client,
    boost::asio::io_context& io_context,
    OrderHandler order_handler,
    FillHandler fill_handler,
    std::function<void()> heartbeat_handler)
    : credentials_(std::move(credentials)),
      rest_client_(std::move(rest_client)),
      io_context_(io_context),
      resolver_(io_context),
      order_handler_(std::move(order_handler)),
      fill_handler_(std::move(fill_handler)),
      heartbeat_handler_(std::move(heartbeat_handler)) {}

PrivateWebSocketSession::~PrivateWebSocketSession() {
    disconnect();
    stop_ = true;
    if (reader_thread_.joinable()) {
        reader_thread_.join();
    }
    if (heartbeat_thread_.joinable()) {
        heartbeat_thread_.join();
    }
}

void PrivateWebSocketSession::connect() {
    stop_ = false;
    try {
        authenticate();
        auto parsed = parseWebsocketUrl(ws_endpoint_);
        if (parsed.secure) {
            throw std::runtime_error(
                "TLS websocket endpoints are not supported without additional SSL setup");
        }
        std::string connect_id = generateConnectId();
        std::string target = parsed.target + "?token=" + ws_token_ + "&connectId=" + connect_id;

        auto ws = std::make_unique<
            boost::beast::websocket::stream<boost::asio::ip::tcp::socket>>(io_context_);
        auto results = resolver_.resolve(parsed.host, parsed.port);
        boost::asio::connect(ws->next_layer(), results.begin(), results.end());
        ws->handshake(parsed.host, target);

        {
            std::lock_guard<std::mutex> lock(ws_mutex_);
            ws_ = std::move(ws);
        }
        connected_ = true;
        startRead();
        scheduleHeartbeat();
    } catch (const std::exception& ex) {
        std::cerr << "Private websocket connect failed: " << ex.what() << std::endl;
        connected_ = false;
        throw;
    }
}

void PrivateWebSocketSession::disconnect() {
    connected_ = false;
    stop_ = true;
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (ws_) {
        boost::system::error_code ec;
        ws_->close(boost::beast::websocket::close_code::normal, ec);
        ws_.reset();
    }
}

void PrivateWebSocketSession::authenticate() {
    long timestamp = toMillisecondsSinceEpoch();
    std::string ts_str = std::to_string(timestamp);
    const std::string endpoint = "/api/v1/bullet-private";
    const std::string body = "{}";
    auto headers = credentials_.buildAuthHeaders("POST", endpoint, "", body, ts_str);
    headers["Content-Type"] = "application/json";
    auto response = rest_client_.request("POST", endpoint, headers, body);
    if (response.status_code != 200) {
        std::ostringstream oss;
        oss << "Failed to fetch websocket token: HTTP " << response.status_code;
        throw std::runtime_error(oss.str());
    }

    auto json = boost::json::parse(response.body);
    auto& obj = json.as_object();
    if (!obj.contains("data")) {
        throw std::runtime_error("Bullet token response missing data field");
    }
    const auto& data = obj.at("data").as_object();
    if (!data.contains("token") || !data.contains("instanceServers")) {
        throw std::runtime_error("Bullet token response missing token or servers");
    }
    ws_token_ = data.at("token").as_string().c_str();
    const auto& servers = data.at("instanceServers").as_array();
    if (servers.empty()) {
        throw std::runtime_error("No websocket servers available");
    }
    const auto& server = servers.front().as_object();
    ws_endpoint_ = server.at("endpoint").as_string().c_str();
    if (auto it = server.find("pingInterval"); it != server.end()) {
        heartbeat_interval_ = std::chrono::milliseconds(
            static_cast<long>(boost::json::value_to<double>(it->value())));
    }
}

void PrivateWebSocketSession::startRead() {
    if (reader_thread_.joinable()) {
        reader_thread_.join();
    }
    reader_thread_ = std::thread([this]() {
        boost::beast::flat_buffer buffer;
        while (!stop_) {
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
                if (!stop_) {
                    connected_ = false;
                    reconnect();
                }
                break;
            }
            auto data = buffer.data();
            std::string message(boost::asio::buffers_begin(data),
                                boost::asio::buffers_end(data));
            buffer.consume(buffer.size());
            handleMessage(message);
        }
    });
}

void PrivateWebSocketSession::scheduleHeartbeat() {
    if (heartbeat_thread_.joinable()) {
        heartbeat_thread_.join();
    }
    heartbeat_thread_ = std::thread([this]() {
        while (!stop_) {
            std::this_thread::sleep_for(heartbeat_interval_);
            if (stop_) {
                break;
            }
            sendPing();
            if (heartbeat_handler_) {
                heartbeat_handler_();
            }
        }
    });
}

void PrivateWebSocketSession::sendPing() {
    std::lock_guard<std::mutex> lock(ws_mutex_);
    if (!ws_ || !connected_) {
        return;
    }
    boost::system::error_code ec;
    ws_->write(boost::asio::buffer(std::string("{\"type\":\"ping\"}")), ec);
    if (ec) {
        connected_ = false;
        reconnect();
    }
}

void PrivateWebSocketSession::reconnect() {
    if (stop_) {
        return;
    }
    {
        std::lock_guard<std::mutex> lock(ws_mutex_);
        if (ws_) {
            boost::system::error_code ec;
            ws_->close(boost::beast::websocket::close_code::normal, ec);
            ws_.reset();
        }
    }
    std::thread([this]() {
        std::this_thread::sleep_for(std::chrono::seconds(3));
        try {
            connect();
        } catch (const std::exception& ex) {
            std::cerr << "Private websocket reconnect failed: " << ex.what() << std::endl;
        }
    }).detach();
}

void PrivateWebSocketSession::handleMessage(const std::string& message) {
    boost::json::value json;
    try {
        json = boost::json::parse(message);
    } catch (const std::exception& ex) {
        std::cerr << "Failed to parse private websocket message: " << ex.what()
                  << " | payload=" << message << std::endl;
        return;
    }
    if (!json.is_object()) {
        return;
    }
    const auto& obj = json.as_object();
    if (!obj.contains("topic")) {
        return;
    }
    const auto& topic = obj.at("topic").as_string();
    if (topic.find("tradeOrders") != std::string::npos) {
        parseOrderMessage(json, order_handler_);
    } else if (topic.find("fills") != std::string::npos) {
        parseFillMessage(json, fill_handler_);
    }
}

}  // namespace kucoin
