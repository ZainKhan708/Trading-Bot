#include <iostream>

#include "kucoin/credentials.hpp"
#include "kucoin/rest_client.hpp"

int main() {
    kucoin::KucoinCredentials creds({"key", "secret", "passphrase", "", false});
    kucoin::RestClient rest_client;
    std::cout << "Trading bot scaffolding initialized." << std::endl;
    (void)creds;
    (void)rest_client;
    return 0;
}
