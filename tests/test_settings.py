import pytest
from pydantic import ValidationError

from app.config.settings import ExchangeProvider, Settings, TradingMode


def test_defaults_are_safe():
    settings = Settings()
    assert settings.trading_mode is TradingMode.PAPER
    assert settings.enable_live_trading is False
    assert settings.max_consecutive_losses == 3


def test_live_requires_explicit_gate():
    with pytest.raises(ValidationError):
        Settings(trading_mode=TradingMode.LIVE, enable_live_trading=True)


def test_live_requires_confirmation_and_credentials():
    settings = Settings(
        trading_mode=TradingMode.LIVE,
        enable_live_trading=True,
        live_trading_confirmation="I_UNDERSTAND_LIVE_RISK",
        binance_api_key="key",
        binance_api_secret="secret",
    )
    assert settings.trading_mode is TradingMode.LIVE


def test_dex_mode_requires_walletconnect_project():
    with pytest.raises(ValidationError):
        Settings(trading_mode=TradingMode.DEX, exchange_provider=ExchangeProvider.DEX)


def test_hyperliquid_is_allowed_for_dex_mode():
    settings = Settings(
        trading_mode=TradingMode.DEX,
        exchange_provider=ExchangeProvider.HYPERLIQUID,
        walletconnect_project_id="project",
        dex_chain_id=8453,
        dex_rpc_url="https://rpc.example",
    )
    assert settings.exchange_provider is ExchangeProvider.HYPERLIQUID


def test_remote_control_requires_token(monkeypatch):
    # The conftest fixture injects CONTROL_API_TOKEN for API tests; clear it
    # so we can exercise the validator's "token required when remote control
    # is enabled" branch.
    monkeypatch.delenv("CONTROL_API_TOKEN", raising=False)
    with pytest.raises(ValidationError, match="CONTROL_API_TOKEN"):
        Settings(_env_file=None, enable_remote_control=True)


def test_dex_requires_chain_and_rpc_configuration():
    with pytest.raises(ValidationError, match="DEX mode requires chain ID and RPC URL"):
        Settings(
            trading_mode=TradingMode.DEX,
            exchange_provider=ExchangeProvider.HYPERLIQUID,
            walletconnect_project_id="project",
        )


def test_testnet_requires_binance_credentials():
    with pytest.raises(ValidationError, match="Testnet mode requires Binance credentials"):
        Settings(_env_file=None, trading_mode=TradingMode.TESTNET, exchange_provider=ExchangeProvider.BINANCE)


def test_invalid_timeframe_is_rejected():
    with pytest.raises(ValidationError, match="TIMEFRAME"):
        Settings(_env_file=None, timeframe="2m")
