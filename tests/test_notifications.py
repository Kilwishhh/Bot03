import pytest
from app.notifications import TelegramNotifier


def test_telegram_requires_configuration():
    with pytest.raises(ValueError):
        TelegramNotifier("", "")