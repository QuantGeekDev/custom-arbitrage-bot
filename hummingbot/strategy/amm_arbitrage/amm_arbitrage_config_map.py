from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_amm,
    validate_market_trading_pair,
    validate_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
    # AMM,
    EXAMPLE_PAIRS,
)
from decimal import Decimal
from typing import Optional


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def secondary_market_on_validated(value: str):
    required_exchanges.append(value)


def validate_primary_market_trading_pair(value: str) -> Optional[str]:
    primary_market = amm_arbitrage_config_map.get("primary_market").value
    return validate_market_trading_pair(primary_market, value)


def validate_secondary_market_trading_pair(value: str) -> Optional[str]:
    secondary_market = amm_arbitrage_config_map.get("secondary_market").value
    return validate_market_trading_pair(secondary_market, value)


def primary_trading_pair_prompt():
    primary_market = amm_arbitrage_config_map.get("primary_market").value
    example = EXAMPLE_PAIRS.get(primary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (primary_market, f" (e.g. {example})" if example else "")


def secondary_trading_pair_prompt():
    secondary_market = amm_arbitrage_config_map.get("secondary_market").value
    example = EXAMPLE_PAIRS.get(secondary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (secondary_market, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = amm_arbitrage_config_map["secondary_market_trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


amm_arbitrage_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="amm_arbitrage"),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your primary (AMM) automated market marking name >>> ",
        prompt_on_new=True,
        validator=validate_amm,
        on_validated=lambda value: required_exchanges.append(value)),
    # validator = validate_exchange,
    #             on_validated = exchange_on_validated),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your secondary exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=exchange_on_validated),
    "primary_market_trading_pair": ConfigVar(
        key="primary_market_trading_pair",
        prompt=primary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_primary_market_trading_pair),
    "secondary_market_trading_pair": ConfigVar(
        key="secondary_market_trading_pair",
        prompt=secondary_trading_pair_prompt,
        prompt_on_new=True,
        # validator=validate_secondary_market_trading_pair),
        validator = lambda x: validate_market_trading_pair(amm_arbitrage_config_map["secondary_market"].value, x)),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        prompt_on_new=True),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "amm_slippage_buffer": ConfigVar(
        key="amm_slippage_buffer",
        prompt="How much buffer do you want to add to the token price to account for slippage (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.01"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
}
