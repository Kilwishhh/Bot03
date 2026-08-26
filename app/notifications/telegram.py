"""Optional Telegram Bot API notifier using the standard library."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .base import Notifier


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str, timeout: float = 10.0) -> None:
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot token and chat ID are required")
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout

    def send(self, message: str) -> None:
        payload = urlencode({"chat_id": self._chat_id, "text": message}).encode()
        request = Request(self._url, data=payload, method="POST")
        with urlopen(request, timeout=self._timeout) as response:
            result = json.loads(response.read())
        if not result.get("ok"):
            raise RuntimeError("Telegram rejected the notification")