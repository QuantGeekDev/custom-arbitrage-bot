from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import logging; logging.basicConfig(level=logging.INFO)
import pandas as pd
import unittest
import asyncio
import time
from decimal import Decimal
from typing import Optional
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    FundingInfo,
    OrderBookTradeEvent,
    TradeType
)
from test.mock.mock_perp_connector import MockPerpConnector
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage import SpotPerpetualArbitrageStrategy
from hummingbot.strategy.spot_perpetual_arbitrage.arb_proposal import ArbProposal


class TestSpotPerpetualArbitrage(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self):
        self.spot_fill_logger: EventLogger = EventLogger()
        self.perp_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1, self.start_timestamp, self.end_timestamp)
        self.spot_connector: BacktestMarket = BacktestMarket()
        self.spot_obook: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.spot_obook.set_balanced_order_book(mid_price=100,
                                                min_price=1,
                                                max_price=200,
                                                price_step_size=2,
                                                volume_step_size=10)
        self.spot_connector.add_data(self.spot_obook)
        self.spot_connector.set_balance("HBOT", 500)
        self.spot_connector.set_balance("ETH", 5000)
        self.spot_connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.spot_market_info = MarketTradingPairTuple(self.spot_connector, self.trading_pair,
                                                       self.base_asset, self.quote_asset)

        self.perp_connector: MockPerpConnector = MockPerpConnector()
        self.perp_obook: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset,
                                                                   self.quote_asset)
        self.perp_obook.set_balanced_order_book(mid_price=110,
                                                min_price=1,
                                                max_price=200,
                                                price_step_size=2,
                                                volume_step_size=10)
        self.perp_connector.add_data(self.perp_obook)
        self.perp_connector.set_balance("HBOT", 500)
        self.perp_connector.set_balance("ETH", 5000)
        self.perp_connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 5, 5, 5, 5
            )
        )
        self.perp_market_info = MarketTradingPairTuple(self.perp_connector, self.trading_pair,
                                                       self.base_asset, self.quote_asset)

        self.clock.add_iterator(self.spot_connector)
        self.clock.add_iterator(self.perp_connector)

        self.spot_connector.add_listener(MarketEvent.OrderFilled, self.spot_fill_logger)
        self.spot_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)
        self.perp_connector.add_listener(MarketEvent.OrderFilled, self.perp_fill_logger)
        self.perp_connector.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.strategy = SpotPerpetualArbitrageStrategy(
            self.spot_market_info,
            self.perp_market_info,
            order_amount=Decimal("1"),
            derivative_leverage=5,
            min_divergence=Decimal("0.01"),
            min_convergence=Decimal("0.01"),
            spot_market_slippage_buffer=Decimal("0.01"),
            derivative_market_slippage_buffer=Decimal("0.01")
        )
        self.current_tick = 1

    def simulate_maker_market_trade(
            self, is_buy: bool, quantity: Decimal, price: Decimal, market: Optional[BacktestMarket] = None,
    ):
        if market is None:
            market = self.market
        order_book = market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def _turn_clock(self, no_ticks: int):
        for i in range(self.current_tick, self.current_tick + no_ticks + 1):
            self.clock.backtest_til(self.start_timestamp + i)
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))

    def test_strategy_starts(self):
        """
        Tests if the strategy can start
        """

        self.clock.add_iterator(self.strategy)
        self.perp_connector._funding_info[self.trading_pair] = FundingInfo(
            self.trading_pair,
            Decimal("100"),
            Decimal("100"),
            time.time() + 10000,
            Decimal("0.00001")
        )
        self._turn_clock(5)
        self._turn_clock(5)
        taker_fill = self.spot_fill_logger.event_log
        print(taker_fill)
        # self.clock.backtest_til(self.start_timestamp + 3)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
        # self.clock.backtest_til(self.start_timestamp + 10)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
        # self.clock.backtest_til(self.start_timestamp + 5)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
        # self.clock.backtest_til(self.start_timestamp + 6)
        # asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))

    def test_arb_proposal(self):
        proposal = ArbProposal(spot_market_info=self.spot_market_info,
                               derivative_market_info=self.perp_market_info,
                               order_amount=1,
                               timestamp=time.time())
        asyncio.get_event_loop().run_until_complete(self._test_arb_proposal_update_prices(proposal))

    async def _test_arb_proposal_update_prices(self, proposal: ArbProposal):
        await proposal.update_prices()
        self.assertEqual(len(proposal.spot_buy_sell_prices), 2)
        self.assertEqual(len(proposal.deriv_buy_sell_prices), 2)
        self.assertEqual(proposal.spot_buy_sell_prices[0], self.spot_obook.order_book.snapshot[1].iloc[0]["price"])
        self.assertEqual(proposal.spot_buy_sell_prices[1], self.spot_obook.order_book.snapshot[0].iloc[0]["price"])
        self.assertEqual(proposal.deriv_buy_sell_prices[0], self.perp_obook.order_book.snapshot[1].iloc[0]["price"])
        self.assertEqual(proposal.deriv_buy_sell_prices[1], self.perp_obook.order_book.snapshot[0].iloc[0]["price"])

        await proposal.proposed_spot_deriv_arb()
        self.assertEqual(proposal.spot_side.is_buy, True)
