import pytest
from app.config import ExchangeProvider, Settings, TradingMode
from app.exchange import PaperTradingAdapter, create_exchange


def test_paper_factory_returns_paper_adapter():
    assert isinstance(create_exchange(Settings()), PaperTradingAdapter)


def test_dex_execution_is_explicitly_unavailable_until_adapter_exists():
    settings = Settings(
        trading_mode=TradingMode.DEX,
        exchange_provider=ExchangeProvider.DEX,
        walletconnect_project_id="project",
    )
    with pytest.raises(NotImplementedError, match="DEX execution is not yet implemented"):
        create_exchange(settings)