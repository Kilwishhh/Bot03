"""Production configuration validation and fail-fast checks."""

from __future__ import annotations

import logging
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from .settings import ExchangeProvider, Settings, TradingMode


logger = logging.getLogger(__name__)

_HEX_TOKEN = re.compile(r"^[0-9a-fA-F]{16,}$")
_API_KEY_HINT = "looks like an API key but contains invalid characters"


class ConfigurationError(RuntimeError):
    """Raised when the runtime configuration is invalid or unsafe."""


def _warn(message: str) -> None:
    logger.warning("config: %s", message)


def _error(message: str) -> None:
    logger.error("config: %s", message)
    raise ConfigurationError(message)


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in ("your_", "changeme", "example", "replace", "todo", "<", ">")
    )


def _validate_credentials_present(settings: Settings) -> None:
    if settings.trading_mode is TradingMode.LIVE and settings.exchange_provider is ExchangeProvider.BINANCE:
        if not settings.binance_api_key or not settings.binance_api_secret:
            _error("Live Binance mode requires both BINANCE_API_KEY and BINANCE_API_SECRET")
    elif settings.trading_mode is TradingMode.TESTNET and settings.exchange_provider is ExchangeProvider.BINANCE:
        if not settings.binance_api_key or not settings.binance_api_secret:
            _warn("Testnet mode without Binance credentials; API calls will fail")


def _validate_credential_format(settings: Settings) -> None:
    if settings.binance_api_key and not _HEX_TOKEN.match(settings.binance_api_key):
        _warn(f"BINANCE_API_KEY {_API_KEY_HINT}")
    if settings.binance_api_secret and not re.match(r"^[A-Za-z0-9/+=]{16,}$", settings.binance_api_secret):
        _warn("BINANCE_API_SECRET has unexpected characters; verify it was pasted correctly")


def _validate_live_safety(settings: Settings) -> None:
    if settings.trading_mode is not TradingMode.LIVE:
        return
    if settings.exchange_provider is ExchangeProvider.BINANCE:
        if not settings.enable_live_trading:
            _error("Live mode requires ENABLE_LIVE_TRADING=true")
        if settings.live_trading_confirmation != "I_UNDERSTAND_LIVE_RISK":
            _error("Live mode requires LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK")


def _validate_dex_safety(settings: Settings) -> None:
    if settings.trading_mode is not TradingMode.DEX:
        return
    if not settings.walletconnect_project_id:
        _error("DEX mode requires WALLETCONNECT_PROJECT_ID")
    if settings.exchange_provider is ExchangeProvider.HYPERLIQUID:
        if not settings.dex_chain_id:
            _error("Hyperliquid DEX mode requires DEX_CHAIN_ID")
        if not settings.dex_rpc_url:
            _error("Hyperliquid DEX mode requires DEX_RPC_URL")
        if settings.hyperliquid_wallet_address and not re.match(r"^0x[a-fA-F0-9]{40}$", settings.hyperliquid_wallet_address):
            _error("HYPERLIQUID_WALLET_ADDRESS must be a valid 0x-prefixed address")


def _validate_remote_control(settings: Settings) -> None:
    if not settings.enable_remote_control:
        return
    if not settings.control_api_token:
        _error("ENABLE_REMOTE_CONTROL=true requires CONTROL_API_TOKEN")
    if len(settings.control_api_token) < 16:
        _warn("CONTROL_API_TOKEN is short; use a high-entropy secret (>= 16 chars)")
    if not settings.admin_api_token:
        _warn("ADMIN_API_TOKEN is not set; admin endpoints will reject all requests")


def _validate_telegram(settings: Settings) -> None:
    if not settings.enable_telegram:
        return
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        _warn("ENABLE_TELEGRAM=true but credentials are missing; notifications will be disabled")


def _validate_risk_bounds(settings: Settings) -> None:
    if settings.risk_per_trade > Decimal("0.05"):
        _warn(f"RISK_PER_TRADE={settings.risk_per_trade} is high (>5%)")
    if settings.max_leverage > 20:
        _warn(f"MAX_LEVERAGE={settings.max_leverage} is aggressive (>20x)")
    if settings.max_daily_loss > Decimal("0.10"):
        _warn(f"MAX_DAILY_LOSS={settings.max_daily_loss} is high (>10%)")


def _validate_persistence(settings: Settings) -> None:
    db_path = Path(settings.database_path)
    parent = db_path.parent if db_path.parent != Path("") else Path(".")
    if not parent.exists():
        _warn(f"Database parent directory does not exist: {parent}")
    if db_path.exists() and not os.access(db_path, os.R_OK | os.W_OK):
        _warn(f"Database file is not readable/writable: {db_path}")


def _validate_no_placeholders(settings: Settings) -> None:
    secret_fields = (
        "binance_api_key",
        "binance_api_secret",
        "telegram_bot_token",
        "walletconnect_project_id",
        "control_api_token",
        "admin_api_token",
    )
    for field_name in secret_fields:
        value = getattr(settings, field_name, "")
        if value and _is_placeholder(value):
            _error(f"{field_name.upper()} appears to contain a placeholder value; replace it before starting")


def _validate_database_writable(settings: Settings) -> None:
    db_path = Path(settings.database_path)
    if db_path.exists():
        return
    try:
        db_path.touch()
        db_path.unlink()
    except OSError as error:
        _error(f"Database path is not writable: {db_path} ({error})")


def validate_startup(settings: Settings, *, strict: bool = False) -> list[str]:
    """Run all startup configuration checks. Returns a list of warnings.

    Set ``strict=True`` to raise on warnings as well.
    """
    warnings: list[str] = []
    checks: Iterable = (
        _validate_no_placeholders,
        _validate_credentials_present,
        _validate_credential_format,
        _validate_live_safety,
        _validate_dex_safety,
        _validate_remote_control,
        _validate_telegram,
        _validate_risk_bounds,
        _validate_persistence,
        _validate_database_writable,
    )
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        for check in checks:
            try:
                check(settings)
            except ConfigurationError:
                raise
            except Exception as error:  # noqa: BLE001
                warnings.append(f"{check.__name__} crashed: {error}")
    finally:
        logger.setLevel(original_level)
    if strict and warnings:
        raise ConfigurationError("strict validation failed: " + "; ".join(warnings))
    return warnings
