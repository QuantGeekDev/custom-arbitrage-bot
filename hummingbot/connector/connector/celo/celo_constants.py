# A single source of truth for constant variables related to the exchange
from decimal import Decimal

UNIT_MULTIPLIER = Decimal(1e18)
CELO_BASE = "CGLD"
CELO_QUOTE = "CUSD"
SYMBOLS_MAP = {CELO_BASE: "gold", CELO_QUOTE: "usd"}
CELO_TRADING_PAIR = "-".join([CELO_BASE, CELO_QUOTE])

EXCHANGE_NAME = "celo"
# REST_URL = "https://api.crypto.com/v2"

API_REASONS = {}
