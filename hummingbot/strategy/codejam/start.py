from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.codejam.codejam import CodejamStrategy
from hummingbot.strategy.codejam.codejam_config_map import codejam_config_map as c_map


def start(self):
    exchange = c_map.get("exchange").value.lower()
    market = c_map.get("market").value

    self._initialize_markets([(exchange, [market])])
    exchange = self.markets[exchange]
    base, quote = market.split("-")
    market_info = MarketTradingPairTuple(exchange, market, base, quote)
    self.strategy = CodejamStrategy(
        exchange=exchange,
        market_info=market_info,
    )
