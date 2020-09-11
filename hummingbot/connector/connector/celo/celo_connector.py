import logging
from typing import (
    Dict,
    List,
    Optional,
)
from decimal import Decimal
import asyncio
import aiohttp

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    MarketEvent,
    # BuyOrderCompletedEvent,
    # SellOrderCompletedEvent,
    # OrderFilledEvent,
    # OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
)
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.connector.celo.celo_cli import (
    CeloCLI,
)

# from .crypto_com_auth import CryptoComAuth
from hummingbot.connector.connector.celo.celo_in_flight_order import CeloInFlightOrder
from hummingbot.connector.connector.celo import celo_utils
from hummingbot.connector.connector.celo import celo_constants as Constants
s_logger = None
s_decimal_NaN = Decimal("nan")
CELO_TRADING_PAIR = Constants.CELO_TRADING_PAIR


class CeloConnector(ConnectorBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 fee_estimates: Dict[bool, Decimal],
                 balance_limits: Dict[str, Decimal],
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__(fee_estimates, balance_limits)
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._status_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "celo"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def in_flight_orders(self) -> Dict[str, CeloInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: CeloInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def start(self, clock: Clock, timestamp: float):
        # self._tx_tracker.c_start(clock, timestamp)
        ConnectorBase.start(self, clock, timestamp)

    def stop(self, clock: Clock):
        ConnectorBase.stop(self, clock)
        # self._async_scheduler.stop()

    async def start_network(self):
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    async def stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            # no api endpoint at the moment but using sync status through CLI
            err_msg = await self.is_node_synced()
            if err_msg is None:
                return NetworkStatus.NOT_CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    def get_balance(self):
        """
        To get the Celo wallet balance through Celo CLI
        """
        balance = CeloCLI.balances()
        return balance

    def is_node_synced(self):
        """
        Validate if the Celo ultra light docker node is sync with blockchain through Celo CLI
        """
        sync_status = CeloCLI.validate_node_synced()
        return sync_status

    def get_exchange_rate(self, order_amount):
        """
        Get the exchange rate for specific order amount
        """
        ex_rates = CeloCLI.exchange_rate(order_amount)
        return ex_rates

    def buy(self, buy_amount: Decimal, price: Decimal, min_cgld_returned: Decimal = None):
        # tx_hash = CeloCLI.buy_cgld(cusd_required, min_cgld_returned=min_cgld_returned)
        order_id: str = celo_utils.get_new_client_order_id(True, CELO_TRADING_PAIR)
        safe_ensure_future(self._create_order(trade_type=TradeType.BUY, price=price, order_id=order_id,
                                              trading_pair=CELO_TRADING_PAIR, amount=buy_amount,
                                              min_returned=min_cgld_returned))
        return order_id

    def sell(self, sell_amount: Decimal, price: Decimal, min_cusd_returned: Decimal = None):
        # tx_hash = CeloCLI.sell_cgld(sell_amount, min_cusd_returned=min_cusd_returned)
        order_id: str = celo_utils.get_new_client_order_id(True, CELO_TRADING_PAIR)
        safe_ensure_future(self._create_order(trade_type=TradeType.SELL, price=price, order_id=order_id,
                                              trading_pair=CELO_TRADING_PAIR, amount=sell_amount,
                                              min_returned=min_cusd_returned))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            price: Decimal,
                            order_type: str,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            min_returned: Decimal):

        # default celo order type
        order_type = OrderType.MARKET

        try:
            if trade_type is TradeType.BUY:
                tx_hash = CeloCLI.buy_cgld(amount, min_cgld_returned=min_returned)
            elif trade_type is TradeType.BUY:
                tx_hash = CeloCLI.sell_cgld(amount, min_cusd_returned=min_returned)
            # exchange_order_id = str(order_result["result"]["order_id"])
            self.logger().info(f"Transaction with hash: {tx_hash}.")

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                # tracked_order.exchange_order_id = exchange_order_id

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Celo for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
