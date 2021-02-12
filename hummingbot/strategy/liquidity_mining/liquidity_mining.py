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
from .data_types import Proposal, PriceSize
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.utils.market_price import token_usd_values_by_mid_pries
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("NaN")
lms_logger = None


class LiquidityMiningStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global lms_logger
        if lms_logger is None:
            lms_logger = logging.getLogger(__name__)
        return lms_logger

    def __init__(self,
                 exchange: ExchangeBase,
                 market_infos: Dict[str, MarketTradingPairTuple],
                 spread: Decimal,
                 reserved_balances: Decimal,
                 market_budget_usd: Decimal,
                 order_refresh_time: float,
                 order_refresh_tolerance_pct: Decimal,
                 inventory_range_multiplier: Decimal = Decimal("1"),
                 volatility_interval: int = 60 * 5,
                 avg_volatility_period: int = 10,
                 volatility_to_spread_multiplier: Decimal = Decimal("1"),
                 status_report_interval: float = 900,
                 hb_app_notification: bool = False):
        super().__init__()
        self._exchange = exchange
        self._market_infos = market_infos
        self._spread = spread
        self._reserved_balances = reserved_balances
        self._market_budget_usd = market_budget_usd
        self._order_refresh_time = order_refresh_time
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._inventory_range_multiplier = inventory_range_multiplier
        self._volatility_interval = volatility_interval
        self._avg_volatility_period = avg_volatility_period
        self._volatility_to_spread_multiplier = volatility_to_spread_multiplier
        self._ev_loop = asyncio.get_event_loop()
        self._status_report_interval = status_report_interval
        self._ready_to_trade = False
        self._refresh_times = {market: 0 for market in market_infos}
        self._token_balances = {}
        self._sell_budgets = {}
        self._buy_budgets = {}
        self._mid_prices = {market: [] for market in market_infos}
        self._cur_mid_prices = {}
        self._volatility = {market: s_decimal_nan for market in self._market_infos}
        self._last_vol_reported = 0.
        self._hb_app_notification = hb_app_notification
        self._mid_price_polling_task = None
        self._start_time_stamp = 0.
        self.add_markets([exchange])

    async def mid_price_polling_loop(self):
        while True:
            try:
                self._cur_mid_prices = await BinanceAPIOrderBookDataSource.get_all_mid_prices()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching Binance mid prices.", exc_info=True)
            finally:
                await asyncio.sleep(0.5)

    def get_mid_price(self, trading_pair: str) -> Decimal:
        # self._market_infos[order.trading_pair].get_mid_price()
        return self._cur_mid_prices[trading_pair]

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
            self._ready_to_trade = self._exchange.ready and len(self._cur_mid_prices) > 0
            if not self._ready_to_trade:
                self.logger().warning(f"{self._exchange.name} is not ready. Please wait...")
                return
            else:
                self.logger().info(f"{self._exchange.name} is ready. Trading started.")
                self.create_budget_allocation()
                self._start_time_stamp = self.current_timestamp

        self._token_balances = self.adjusted_available_balances()
        self.update_mid_prices()
        self.update_volatility()
        proposals = self.create_base_proposals()
        self.apply_budget_constraint(proposals)
        self.cancel_active_orders(proposals)
        self.execute_orders_proposal(proposals)

    async def active_orders_df(self) -> pd.DataFrame:
        columns = ["Market", "Side", "Spread", "Size ($)", "Age"]
        data = []
        active_orders = sorted(self.active_orders, key=lambda o: (o.trading_pair, o.is_buy))
        for order in active_orders:
            mid_price = self.get_mid_price(order.trading_pair)
            spread = 0 if mid_price == 0 else abs(order.price - mid_price) / mid_price
            size_usd = self.usd_value(order.trading_pair.split("-")[0]) * order.quantity
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:]) / 1e6,
                                   unit='s').strftime('%H:%M:%S')
            data.append([
                order.trading_pair,
                "buy" if order.is_buy else "sell",
                f"{spread:.2%}",
                f"{size_usd:.0f}",
                age
            ])

        return pd.DataFrame(data=data, columns=columns)

    def market_status_df(self) -> pd.DataFrame:
        data = []
        columns = ["Market", "Mid Price", "Volatility"]
        for market, market_info in self._market_infos.items():
            mid_price = self.get_mid_price(market)
            data.append([
                market,
                float(mid_price),
                "" if self._volatility[market].is_nan() else f"{self._volatility[market]:.2%}",
            ])
        return pd.DataFrame(data=data, columns=columns).replace(np.nan, '', regex=True)

    async def format_status(self) -> str:
        if not self._ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(list(self._market_infos.values())))

        lines.extend(["", "  Markets:"] + ["    " + line for line in
                                           self.market_status_df().to_string(index=False).split("\n")])

        # See if there're any open orders.
        if len(self.active_orders) > 0:
            df = await self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

        warning_lines.extend(self.balance_warning(list(self._market_infos.values())))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def start(self, clock: Clock, timestamp: float):
        self._mid_price_polling_task = safe_ensure_future(self.mid_price_polling_loop())

    def stop(self, clock: Clock):
        if self._mid_price_polling_task is not None:
            self._mid_price_polling_task.cancel()

    def create_base_proposals(self):
        proposals = []
        for market, market_info in self._market_infos.items():
            spread = self._spread
            if self.current_timestamp - self._start_time_stamp < self._volatility_interval * 2:
                spread *= Decimal("3")
            spread = max(spread, self._volatility[market] * self._volatility_to_spread_multiplier)
            mid_price = self.get_mid_price(market)
            buy_price = mid_price * (Decimal("1") - spread)
            buy_price = self._exchange.quantize_order_price(market, buy_price)
            buy_size = self.calc_buy_size(market, buy_price)
            sell_price = mid_price * (Decimal("1") + spread)
            sell_price = self._exchange.quantize_order_price(market, sell_price)
            sell_size = self.calc_sell_size(market, sell_price)
            proposals.append(Proposal(market, PriceSize(buy_price, buy_size), PriceSize(sell_price, sell_size)))
        return proposals

    def calc_buy_size(self, market: str, price: Decimal):
        quote_size = self._buy_budgets[market]
        buy_fee = estimate_fee(self._exchange.name, True)
        buy_size = quote_size / (price * (Decimal("1") + buy_fee.percent))
        buy_size = self._exchange.quantize_order_amount(market, buy_size, price)
        return buy_size

    def calc_sell_size(self, market: str, price: Decimal):
        sell_size = self._sell_budgets[market]
        sell_size = self._exchange.quantize_order_amount(market, sell_size, price)
        return sell_size

    def usd_value(self, token: str) -> Decimal:
        token_usd_values = token_usd_values_by_mid_pries(self._cur_mid_prices)
        return token_usd_values.get(token, s_decimal_zero)

    def create_budget_allocation(self):
        # Equally assign buy and sell budgets to all markets
        # self._sell_budgets = {m: s_decimal_zero for m in self._market_infos}
        # self._buy_budgets = {m: s_decimal_zero for m in self._market_infos}
        # if self._token == list(self._market_infos.keys())[0].split("-")[0]:
        #     base_markets = [m for m in self._market_infos if m.split("-")[0] == self._token]
        #     sell_size = self._exchange.get_available_balance(self._token) / len(base_markets)
        #     for market in base_markets:
        #         self._sell_budgets[market] = sell_size
        #         self._buy_budgets[market] = self._exchange.get_available_balance(market.split("-")[1])
        # else:
        #     quote_markets = [m for m in self._market_infos if m.split("-")[1] == self._token]
        #     buy_size = self._exchange.get_available_balance(self._token) / len(quote_markets)
        #     for market in quote_markets:
        #         self._buy_budgets[market] = buy_size
        #         self._sell_budgets[market] = self._exchange.get_available_balance(market.split("-")[0])

        # Equally assign buy and sell budgets to all markets
        max_budget_usd = self._market_budget_usd
        total_budget = {m: max_budget_usd for m in self._market_infos}
        base_tokens = self.all_base_tokens()
        self._sell_budgets = {m: s_decimal_zero for m in self._market_infos}
        balances = self.adjusted_available_balances()
        for base in base_tokens:
            base_markets = [m for m in self._market_infos if m.split("-")[0] == base]
            sell_size = balances[base] / len(base_markets)
            for market in base_markets:
                sell_value = sell_size * self.usd_value(base)
                sell_value = min(total_budget[market], sell_value)
                total_budget[market] -= sell_value
                if self.usd_value(base) > 0:
                    self._sell_budgets[market] = sell_value / self.usd_value(base)
        # Then assign all the buy order size based on the quote token balance available
        quote_tokens = self.all_quote_tokens()
        self._buy_budgets = {m: s_decimal_zero for m in self._market_infos}
        for quote in quote_tokens:
            quote_markets = [m for m in self._market_infos if m.split("-")[1] == quote]
            buy_size = balances[quote] / len(quote_markets)
            for market in quote_markets:
                buy_value = buy_size * self.usd_value(quote)
                buy_value = min(total_budget[market], buy_value)
                if self.usd_value(quote) > 0:
                    self._buy_budgets[market] = buy_value / self.usd_value(quote)
        pass

    def apply_budget_constraint(self, proposals: List[Proposal]):
        balances = self._token_balances.copy()
        for proposal in proposals:
            if balances[proposal.base()] < proposal.sell.size:
                proposal.sell.size = balances[proposal.base()]
            proposal.sell.size = self._exchange.quantize_order_amount(proposal.market, proposal.sell.size,
                                                                      proposal.sell.price)
            balances[proposal.base()] -= proposal.sell.size

            quote_size = proposal.buy.size * proposal.buy.price
            if balances[proposal.quote()] < quote_size:
                quote_size = balances[proposal.quote()]
            buy_fee = estimate_fee(self._exchange.name, True)
            buy_size = quote_size / (proposal.buy.price * (Decimal("1") + buy_fee.percent))
            proposal.buy.size = self._exchange.quantize_order_amount(proposal.market, buy_size, proposal.buy.price)
            balances[proposal.quote()] -= quote_size

    def is_within_tolerance(self, cur_orders: List[LimitOrder], proposal: Proposal):
        cur_buy = [o for o in cur_orders if o.is_buy]
        cur_sell = [o for o in cur_orders if not o.is_buy]
        if (cur_buy and proposal.buy.size <= 0) or (cur_sell and proposal.sell.size <= 0):
            return False
        if cur_buy and \
                abs(proposal.buy.price - cur_buy[0].price) / cur_buy[0].price > self._order_refresh_tolerance_pct:
            return False
        if cur_sell and \
                abs(proposal.sell.price - cur_sell[0].price) / cur_sell[0].price > self._order_refresh_tolerance_pct:
            return False
        return True

    def cancel_active_orders(self, proposals: List[Proposal]):
        for proposal in proposals:
            if self._refresh_times[proposal.market] > self.current_timestamp:
                continue
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if not cur_orders or self.is_within_tolerance(cur_orders, proposal):
                continue
            for order in cur_orders:
                self.cancel_order(self._market_infos[proposal.market], order.client_order_id)
                # To place new order on the next tick
                self._refresh_times[order.trading_pair] = self.current_timestamp + 0.1

    def execute_orders_proposal(self, proposals: List[Proposal]):
        for proposal in proposals:
            cur_orders = [o for o in self.active_orders if o.trading_pair == proposal.market]
            if cur_orders or self._refresh_times[proposal.market] > self.current_timestamp:
                continue
            mid_price = self.get_mid_price(proposal.market)
            spread = s_decimal_zero
            if proposal.buy.size > 0:
                spread = abs(proposal.buy.price - mid_price) / mid_price
                self.logger().info(f"({proposal.market}) Creating a bid order {proposal.buy} value: "
                                   f"{proposal.buy.size * proposal.buy.price:.2f} {proposal.quote()} spread: "
                                   f"{spread:.2%}")
                self.buy_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.buy.size,
                    order_type=OrderType.LIMIT_MAKER,
                    price=proposal.buy.price
                )
            if proposal.sell.size > 0:
                spread = abs(proposal.sell.price - mid_price) / mid_price
                self.logger().info(f"({proposal.market}) Creating an ask order at {proposal.sell} value: "
                                   f"{proposal.sell.size * proposal.sell.price:.2f} {proposal.quote()} spread: "
                                   f"{spread:.2%}")
                self.sell_with_specific_market(
                    self._market_infos[proposal.market],
                    proposal.sell.size,
                    order_type=OrderType.LIMIT_MAKER,
                    price=proposal.sell.price
                )
            if proposal.buy.size > 0 or proposal.sell.size > 0:
                if not self._volatility[proposal.market].is_nan() and spread > self._spread:
                    adjusted_vol = self._volatility[proposal.market] * self._volatility_to_spread_multiplier
                    if adjusted_vol > self._spread:
                        self.logger().info(f"({proposal.market}) Spread is widened to {spread:.2%} due to high "
                                           f"market volatility")

                self._refresh_times[proposal.market] = self.current_timestamp + self._order_refresh_time

    def all_base_tokens(self) -> Set[str]:
        tokens = set()
        for market in self._market_infos:
            tokens.add(market.split("-")[0])
        return tokens

    def all_quote_tokens(self) -> Set[str]:
        tokens = set()
        for market in self._market_infos:
            tokens.add(market.split("-")[1])
        return tokens

    def all_tokens(self) -> Set[str]:
        tokens = set()
        for market in self._market_infos:
            tokens.update(market.split("-"))
        return tokens

    def adjusted_available_balances(self) -> Dict[str, Decimal]:
        """
        Calculates all available balances, account for amount attributed to orders and reserved balance.
        :return: a dictionary of token and its available balance
        """
        tokens = self.all_tokens()
        adjusted_bals = {t: s_decimal_zero for t in tokens}
        total_bals = {t: s_decimal_zero for t in tokens}
        total_bals.update(self._exchange.get_all_balances())
        for token in tokens:
            adjusted_bals[token] = self._exchange.get_available_balance(token)
        for order in self.active_orders:
            base, quote = order.trading_pair.split("-")
            if order.is_buy:
                adjusted_bals[quote] += order.quantity * order.price
            else:
                adjusted_bals[base] += order.quantity
        for token in tokens:
            adjusted_bals[token] = min(adjusted_bals[token], total_bals[token])
            reserved = self._reserved_balances.get(token, s_decimal_zero)
            adjusted_bals[token] -= reserved
            adjusted_bals[token] = max(adjusted_bals[token], s_decimal_zero)
        return adjusted_bals

    def did_fill_order(self, event):
        order_id = event.order_id
        market_info = self.order_tracker.get_shadow_market_pair_from_order_id(order_id)
        if market_info is not None:
            if event.trade_type is TradeType.BUY:
                msg = f"({market_info.trading_pair}) Maker BUY order (price: {event.price}) of {event.amount} " \
                      f"{market_info.base_asset} is filled."
                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app(msg)
                self._buy_budgets[market_info.trading_pair] -= (event.amount * event.price)
                self._sell_budgets[market_info.trading_pair] += event.amount
            else:
                msg = f"({market_info.trading_pair}) Maker SELL order (price: {event.price}) of {event.amount} " \
                      f"{market_info.base_asset} is filled."
                self.log_with_clock(logging.INFO, msg)
                self.notify_hb_app(msg)
                self._sell_budgets[market_info.trading_pair] -= event.amount
                self._buy_budgets[market_info.trading_pair] += (event.amount * event.price)

    def update_mid_prices(self):
        for market in self._market_infos:
            mid_price = self.get_mid_price(market)
            self._mid_prices[market].append(mid_price)
            # To avoid memory leak, we store only the last part of the list needed for volatility calculation and spread bias
            max_len = self._volatility_interval * self._avg_volatility_period * 10
            self._mid_prices[market] = self._mid_prices[market][-1 * max_len:]

    def update_volatility(self):
        self._volatility = {market: s_decimal_nan for market in self._market_infos}
        for market, mid_prices in self._mid_prices.items():
            last_index = len(mid_prices) - 1
            atr = []
            first_index = last_index - (self._volatility_interval * self._avg_volatility_period)
            first_index = max(first_index, 0)
            for i in range(last_index, first_index, self._volatility_interval * -1):
                prices = mid_prices[i - self._volatility_interval + 1: i + 1]
                if not prices:
                    break
                atr.append((max(prices) - min(prices)) / min(prices))
            if atr:
                self._volatility[market] = mean(atr)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)
