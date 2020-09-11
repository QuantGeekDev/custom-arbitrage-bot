from typing import (
    List,
    Tuple,
)
from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.arbitrage.arbitrage_market_pair import AMMArbitrageMarketPair
from hummingbot.strategy.arbitrage.arbitrage import AMMArbitrageStrategy
from hummingbot.strategy.arbitrage.amm_arbitrage_config_map import amm_arbitrage_config_map


def start(self):
    primary_market = amm_arbitrage_config_map.get("primary_market").value.lower()
    secondary_market = amm_arbitrage_config_map.get("secondary_market").value.lower()
    raw_primary_trading_pair = amm_arbitrage_config_map.get("primary_market_trading_pair").value
    raw_secondary_trading_pair = amm_arbitrage_config_map.get("secondary_market_trading_pair").value
    # order_amount = amm_arbitrage_config_map.get("order_amount").value
    min_profitability = amm_arbitrage_config_map.get("min_profitability").value / Decimal("100")
    # amm_slippage_buffer = amm_arbitrage_config_map.get("amm_slippage_buffer").value / Decimal("100")

    try:
        primary_trading_pair: str = raw_primary_trading_pair
        secondary_trading_pair: str = raw_secondary_trading_pair
        primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [primary_trading_pair])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                           [secondary_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(primary_market, [primary_trading_pair]),
                                                 (secondary_market, [secondary_trading_pair])]
    self._initialize_wallet(token_trading_pairs=list(set(primary_assets + secondary_assets)))
    self._initialize_markets(market_names)
    self.assets = set(primary_assets + secondary_assets)

    primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
    self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data)]
    self.market_pair = AMMArbitrageMarketPair(*self.market_trading_pair_tuples)
    self.strategy = AMMArbitrageStrategy(market_pairs=[self.market_pair],
                                         min_profitability=min_profitability,
                                         logging_options=AMMArbitrageStrategy.OPTION_LOG_ALL,
                                         hb_app_notification=True)
