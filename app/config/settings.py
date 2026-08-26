"""Application configuration with conservative trading defaults."""

from enum import StrEnum
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"
    BACKTEST = "backtest"
    DEX = "dex"


class ExchangeProvider(StrEnum):
    BINANCE = "binance"
    DEX = "dex"
    HYPERLIQUID = "hyperliquid"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trading_mode: TradingMode = TradingMode.PAPER
    exchange_provider: ExchangeProvider = ExchangeProvider.BINANCE
    enable_live_trading: bool = False
    live_trading_confirmation: str = ""
    binance_api_key: str = ""
    binance_api_secret: str = ""
    default_symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    poll_interval_seconds: float = Field(default=60, gt=0)
    api_allowed_origins: str = "http://localhost:3000,http://localhost:8080"
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.05)
    max_daily_loss: float = Field(default=0.03, gt=0, le=1)
    max_open_positions: int = Field(default=3, ge=1)
    max_leverage: int = Field(default=5, ge=1)
    max_exposure: float = Field(default=1000, gt=0)
    max_consecutive_losses: int = Field(default=3, ge=1)
    min_signal_confidence: float = Field(default=0.70, ge=0, le=1)
    strategy: str = "indicator"
    ema_fast: int = Field(default=20, ge=2)
    ema_slow: int = Field(default=50, ge=3)
    rsi_period: int = Field(default=14, ge=2)
    bb_period: int = Field(default=20, ge=2)
    adx_period: int = Field(default=14, ge=2)
    enable_telegram: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    walletconnect_project_id: str = ""
    dex_chain_id: int | None = None
    dex_rpc_url: str = ""
    hyperliquid_api_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_wallet_address: str = ""
    enable_remote_control: bool = False
    control_api_token: str = ""
    admin_api_token: str = ""
    database_path: str = "trading.db"
    retention_days: int = Field(default=90, ge=1)
    alert_failure_threshold: int = Field(default=3, ge=1)
    alert_cooldown_seconds: int = Field(default=900, ge=0)
    prometheus_enabled: bool = False
    log_level: str = "INFO"

    @model_validator(mode="before")
    @classmethod
    def validate_market_defaults(cls, values):
        timeframe = values.get("TIMEFRAME", values.get("timeframe", "15m")) if isinstance(values, dict) else "15m"
        if timeframe not in {"1m", "5m", "15m", "1h", "4h"}:
            raise ValueError("TIMEFRAME must be one of 1m, 5m, 15m, 1h, or 4h")
        return values

    @model_validator(mode="after")
    def enforce_live_safety(self) -> "Settings":
        if self.strategy != "indicator":
            raise ValueError("unsupported strategy; use the registered strategy name 'indicator'")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("EMA_FAST must be lower than EMA_SLOW")
        if self.trading_mode is TradingMode.DEX and self.exchange_provider not in (ExchangeProvider.DEX, ExchangeProvider.HYPERLIQUID):
            raise ValueError("DEX mode requires a DEX provider")
        if self.exchange_provider in (ExchangeProvider.DEX, ExchangeProvider.HYPERLIQUID) and self.trading_mode not in (TradingMode.DEX, TradingMode.PAPER):
            raise ValueError("DEX providers support only paper or dex mode")
        if self.trading_mode is TradingMode.LIVE and self.exchange_provider is ExchangeProvider.BINANCE:
            if not self.enable_live_trading:
                raise ValueError("Live mode requires ENABLE_LIVE_TRADING=true")
            if self.live_trading_confirmation != "I_UNDERSTAND_LIVE_RISK":
                raise ValueError("Live mode requires explicit confirmation")
            if not self.binance_api_key or not self.binance_api_secret:
                raise ValueError("Live mode requires Binance credentials")
        if self.trading_mode is TradingMode.TESTNET and self.exchange_provider is ExchangeProvider.BINANCE:
            if not self.binance_api_key or not self.binance_api_secret:
                raise ValueError("Testnet mode requires Binance credentials")
        if self.trading_mode is TradingMode.DEX:
            if not self.walletconnect_project_id:
                raise ValueError("DEX mode requires WalletConnect project configuration")
            if self.exchange_provider is ExchangeProvider.HYPERLIQUID and (self.dex_chain_id is None or not self.dex_rpc_url):
                raise ValueError("DEX mode requires chain ID and RPC URL")
        if self.enable_remote_control and not self.control_api_token:
            raise ValueError("Remote control requires CONTROL_API_TOKEN when ENABLE_REMOTE_CONTROL=true")
        return self
