from decimal import Decimal
import logging
import asyncio
from typing import Dict, List, Set
import pandas as pd
import numpy as np
from statistics import mean
import time
from hummingbot.core.clock import Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.strategy.pure_market_making.inventory_skew_calculator import (
    calculate_bid_ask_ratios_from_base_asset_ratio
)
NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("NaN")
lms_logger = None


class CodejamStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lms_logger
        if lms_logger is None:
            lms_logger = logging.getLogger(__name__)
        return lms_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 market_info: MarketTradingPairTuple,
                 ):
        super().__init__()
        self._exchange = exchange
        self._market_info = market_info
        self.add_markets([exchange])

    @property
    def active_orders(self):
        limit_orders = self.order_tracker.active_limit_orders
        return [o[1] for o in limit_orders]

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._ready_to_trade:
            # Check if there are restored orders, they should be canceled before strategy starts.
            self._ready_to_trade = self._exchange.ready
            if not self._exchange.ready:
                self.logger().warning(f"{self._exchange.name} is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self._exchange.name} is ready. Trading started.")

        self._last_timestamp = timestamp

    async def format_status(self) -> str:
        if not self._ready_to_trade:
            return "Market connectors are not ready."
        return "to be implemented"

    def start(self, clock: Clock, timestamp: float):
        pass

    def stop(self, clock: Clock):
        pass

