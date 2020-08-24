from decimal import Decimal
from typing import (
    Dict,
    List)
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.network_iterator import NetworkIterator
from hummingbot.market.in_flight_order_base import InFlightOrderBase
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.client.config.global_config_map import (
    global_config_map,
)
NaN = float("nan")
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


cdef class ConnectorBase(NetworkIterator):
    MARKET_EVENTS = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderExpired
    ]

    def __init__(self):
        super().__init__()
        self._event_reporter = EventReporter(event_source=self.name)
        self._event_logger = EventLogger(event_source=self.name)
        for event_tag in self.MARKET_EVENTS:
            self.c_add_listener(event_tag.value, self._event_reporter)
            self.c_add_listener(event_tag.value, self._event_logger)

        self._account_balances = {}  # Dict[asset_name:str, Decimal]
        self._account_available_balances = {}  # Dict[asset_name:str, Decimal]
        self._asset_limit = {}  # Dict[asset_name: str, Decimal]

    @property
    def _account_balances(self):
        return self._account_balances

    @property
    def _account_available_balances(self):
        return self._account_available_balances

    @property
    def _event_reporter(self):
        return self._event_reporter

    @property
    def _event_logger(self):
        return self._event_logger

    @property
    def _current_timestamp(self):
        return self._current_timestamp

    @staticmethod
    def in_flight_asset_balances(in_flight_orders: Dict[str, InFlightOrderBase]) -> Dict[str, Decimal]:
        """
        Calculates the individual asset balances used in in_flight_orders
        For BUY order, this is the quote asset balance locked in the order
        For SELL order, this is the base asset balance locked in the order
        """
        asset_balances = {}
        for order in [o for o in in_flight_orders.values() if not (o.is_done or o.is_failure or o.is_cancelled)]:
            if order.trade_type is TradeType.BUY:
                order_value = Decimal(order.amount * order.price)
                outstanding_value = order_value - order.executed_amount_quote
                if order.quote_asset not in asset_balances:
                    asset_balances[order.quote_asset] = s_decimal_0
                asset_balances[order.quote_asset] += outstanding_value
            else:
                outstanding_value = order.amount - order.executed_amount_base
                if order.base_asset not in asset_balances:
                    asset_balances[order.base_asset] = s_decimal_0
                asset_balances[order.base_asset] += outstanding_value
        return asset_balances

    def get_exchange_limit_config(self, market: str) -> Dict[str, object]:
        """
        Retrieves the Balance Limits for the specified market.
        """
        all_ex_limit = global_config_map["balance_asset_limit"].value
        exchange_limits = all_ex_limit.get(market, {})
        return exchange_limits if exchange_limits is not None else {}

    def order_filled_balances(self):
        """
        Calculates the individual asset balances as a result of order being filled
        For BUY filled order, the quote balance goes down while the base balance goes up, and for SELL order, it's the
        opposite. This does not account for fee.
        """
        order_filled_events = list(filter(lambda e: isinstance(e, OrderFilledEvent), self.event_logs))
        balances = {}
        for event in order_filled_events:
            hb_trading_pair = self.convert_from_exchange_trading_pair(event.trading_pair)
            base, quote = hb_trading_pair.split("-")[0], hb_trading_pair.split("-")[1]
            if event.trade_type is TradeType.BUY:
                quote_value = Decimal("-1") * event.price * event.amount
                base_value = event.amount
            else:
                quote_value = event.price * event.amount
                base_value = Decimal("-1") * event.amount
            if base not in balances:
                balances[base] = s_decimal_0
            if quote not in balances:
                balances[quote] = s_decimal_0
            balances[base] += base_value
            balances[quote] += quote_value
        return balances

    @property
    def status_dict(self) -> Dict[str, bool]:
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def event_logs(self) -> List[any]:
        return self._event_logger.event_log

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrderBase]:
        raise NotImplementedError

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {}

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restores the tracking states from a previously saved state.

        :param saved_states: Previously saved tracking states from `tracking_states` property.
        """
        pass

    def tick(self, timestamp: float):
        raise NotImplementedError

    cdef c_tick(self, double timestamp):
        NetworkIterator.c_tick(self, timestamp)
        self.tick(timestamp)

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        raise NotImplementedError

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN, dict kwargs={}):
        return self.buy(trading_pair, amount, order_type, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        raise NotImplementedError

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        return self.sell(trading_pair, amount, order_type, price)

    cdef c_cancel(self, str trading_pair, str client_order_id):
        self.cancel(trading_pair, client_order_id)

    def cancel(self, trading_pair: str, client_order_id: str):
        raise NotImplementedError

    cdef c_stop_tracking_order(self, str order_id):
        raise NotImplementedError

    def stop_tracking_order(self, order_id: str):
        raise NotImplementedError

    def get_all_balances(self) -> Dict[str, Decimal]:
        """
        *required
        :return: Dict[asset_name: asst_balance]: Balances of all assets being traded
        """
        return self._account_balances.copy()

    cdef object c_get_balance(self, str currency):
        self.get_balance(currency)

    def get_balance(self, currency: str) -> Decimal:
        return self._account_balances.get(currency, s_decimal_0)

    def available_balance_limit_applied(self, currency: str, limit: Decimal) -> Decimal:
        """
        Apply budget limit on an available balance, the limit is calculated as followings:
        - Minus balance used in outstanding orders (in flight orders), if the budget is 1 ETH and the bot has already
          used 0.5 ETH to put a maker buy order, the budget is now 0.5
        - Plus balance accredited from filled orders (since the bot started), if the budget is 1 ETH and the bot has
          bought LINK (for 0.5 ETH), the ETH budget is now 0.5. However if later on the bot has sold LINK (for 0.5 ETH)
          the budget is now 1 ETH
        """
        in_flight_balance = self.in_flight_asset_balances(self.in_flight_orders).get(currency, s_decimal_0)
        limit -= in_flight_balance
        filled_balance = self.order_filled_balances().get(currency, s_decimal_0)
        limit += filled_balance
        asset_limit = max(limit, s_decimal_0)
        available_balance = self._account_available_balances.get(currency, s_decimal_0)
        return min(available_balance, asset_limit)

    cdef object c_get_available_balance(self, str currency):
        return self.get_available_balance(currency)

    def get_available_balance(self, currency: str) -> Decimal:
        """
        If there is a budget limit set on the balance
        :returns: Balance available for trading for a specific asset
        """
        if currency in self.get_exchange_limit_config(self.name):
            asset_limit = Decimal(str(self._asset_limit[currency]))
            return self.available_balance_limit_applied(currency, asset_limit)
        else:
            return self._account_available_balances.get(currency, s_decimal_0)

    cdef object c_get_price(self, str trading_pair, bint is_buy):
        self.get_price(trading_pair, is_buy)

    def get_price(self, trading_pair: str, is_buy: bool, amount: Decimal = s_decimal_NaN) -> Decimal:
        raise NotImplementedError

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        return self.get_order_price_quantum(trading_pair, price)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        raise NotImplementedError

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        return self.get_order_size_quantum(trading_pair, order_size)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        raise NotImplementedError

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        if price.is_nan():
            return price
        price_quantum = self.c_get_order_price_quantum(trading_pair, price)
        return round(price / price_quantum) * price_quantum

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        return self.c_quantize_order_price(trading_pair, price)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_NaN):
        order_size_quantum = self.c_get_order_size_quantum(trading_pair, amount)
        return (amount // order_size_quantum) * order_size_quantum

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        return self.c_quantize_order_amount(trading_pair, amount)
