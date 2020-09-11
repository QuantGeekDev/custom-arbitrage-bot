import math
import time
import random
from typing import List

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from . import celo_constants as Constants


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return math.floor(time.time() * 1e3)


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        cls._request_id += 1
        # return cls._request_id
        return math.floor(random.random() * 1e18)


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "buy" if is_buy else "sell"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


def get_api_reason(code: str) -> str:
    return Constants.API_REASONS.get(int(code), code)
