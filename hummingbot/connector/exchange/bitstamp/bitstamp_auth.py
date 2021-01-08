import hashlib
import hmac
import uuid
import time

from typing import Dict, Any
from urllib.parse import urlencode


class BitstampAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self,
                           http_method: str,
                           path_url: str,
                           query: str = "",
                           params: Dict[str, Any] = None
                           ) -> Dict[str, str]:
        """
        Generates authentication signature and returns it in request parameters
        :return: a string of request parameters including the signature
        """

        nonce: str = str(uuid.uuid4())
        timestamp: str = str(int(round(time.time() * 1000)))
        content_type = ""

        headers = {
            'X-Auth': 'BITSTAMP ' + self.api_key,
            'X-Auth-Nonce': nonce,
            'X-Auth-Timestamp': timestamp,
            'X-Auth-Version': 'v2',
        }

        if http_method == "POST":
            # Defaults to dummy payload if params are not provided
            payload = params if params else {'offset': '1'}
            content_type = "application/x-www-form-urlencoded"
            headers["Content-Type"] = content_type

        message: str = "BITSTAMP" + " " + self.api_key + \
                       http_method + \
                       "www.bitstamp.net/api/v2/" + \
                       path_url + \
                       query + \
                       content_type + \
                       nonce + \
                       timestamp + \
                       "v2" + \
                       urlencode(payload)

        # Calculate signature
        signature: str = hmac.new(
            self.secret_key.encode(),
            message.encode("utf-8"),
            hashlib.sha256).hexdigest()
        headers["X-Auth-Signature"] = signature

        return {
            "key": self.api_key,
            "message": message,
            "headers": headers,
            "params": urlencode(payload)
        }
