#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
import mock
from nose.plugins.attrib import attr
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from .fixture import outputs as celo_outputs
from hummingbot.connector.connector.celo.celo_connector import CeloConnector


MOCK_CELO_COMMANDS = True


def mock_command(commands):
    commands = tuple(commands)
    print(f"command: {commands}")
    print(f"output: {celo_outputs[commands]}")
    return celo_outputs[commands]


@attr('stable')
class CeloConnectorUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "CGLD-CUSD"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    @classmethod
    def setUpClass(cls):
        if MOCK_CELO_COMMANDS:
            cls._patcher = mock.patch("hummingbot.connector.connector.celo.celo_cli.command")
            cls._mock = cls._patcher.start()
            cls._mock.side_effect = mock_command

    @classmethod
    def tearDownClass(cls) -> None:
        if MOCK_CELO_COMMANDS:
            cls._patcher.stop()

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market = CeloConnector()
        self.clock.add_iterator(self.market)
        # self.market.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
        # CeloCLI.unlock_account(TEST_ADDRESS, TEST_PASSWORD)

    def test_get_balances(self):
        balances = self.market.get_all_balances()
        print(balances)
