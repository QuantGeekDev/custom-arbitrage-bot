from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
)
from hummingbot.client.settings import (
    required_exchanges,
)


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


codejam_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="codejam"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter your liquidity mining exchange name >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True),
    "market":
        ConfigVar(key="markets",
                  prompt="Enter a market >>> ",
                  type_str="str",
                  prompt_on_new=True),
}
