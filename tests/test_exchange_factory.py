import pytest
from app.config import ExchangeProvider, Settings, TradingMode
from app.exchange import HyperliquidAdapter, PaperTradingAdapter, create_exchange


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


def test_hyperliquid_factory_returns_hyperliquid_adapter():
    settings = Settings(
        trading_mode=TradingMode.PAPER,
        exchange_provider=ExchangeProvider.HYPERLIQUID,
        hyperliquid_wallet_address="0xtest",
    )
    adapter = create_exchange(settings)
    assert isinstance(adapter, HyperliquidAdapter)
    assert adapter._wallet_address == "0xtest"


def test_hyperliquid_factory_works_for_dex_mode():
    settings = Settings(
        trading_mode=TradingMode.DEX,
        exchange_provider=ExchangeProvider.HYPERLIQUID,
        walletconnect_project_id="project",
        dex_chain_id=8453,
        dex_rpc_url="https://rpc.example",
        hyperliquid_wallet_address="0xtest",
    )
    adapter = create_exchange(settings)
    assert isinstance(adapter, HyperliquidAdapter)