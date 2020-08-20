from typing import Dict
from decimal import Decimal
from hummingbot.connector.connector_base import ConnectorBase


class CeloConnector(ConnectorBase):
    def __init__(self, asset_limits: Dict[str, Decimal] = {}):
        super().__init__(asset_limits)

    def buy(self, trading_pair: str, amount: Decimal, price: Decimal) -> str:
        raise NotImplementedError

    def sell(self, trading_pair: str, amount: Decimal, price: Decimal) -> str:
        raise NotImplementedError
