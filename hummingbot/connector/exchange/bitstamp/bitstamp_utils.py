#!/usr/bin/env/python
from typing import Optional

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"
DEFAULT_FEES = [0.5, 0.5]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Bitstamp uses lowercase (btcusd)
    return hb_trading_pair.replace("-", "").lower()


KEYS = {
    "bitstamp_api_key":
        ConfigVar(key="bitstamp_api_key",
                  prompt="Enter your Crypto.com API key >>> ",
                  required_if=using_exchange("bitstamp"),
                  is_secure=True,
                  is_connect_key=True),
    "bitstamp_secret_key":
        ConfigVar(key="bitstamp_secret_key",
                  prompt="Enter your Crypto.com secret key >>> ",
                  required_if=using_exchange("bitstamp"),
                  is_secure=True,
                  is_connect_key=True),
}
