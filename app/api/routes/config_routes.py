"""Admin config routes — paper trading configuration."""
import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "paper_config.json"

# Default paper config
DEFAULTS = {
    "paper_starting_balance": 10000.0,
    "paper_position_notional": 10.0,
    "max_leverage": 10,
    "risk_per_trade": 0.01,
    "max_open_positions": 3,
    "min_signal_confidence": 0.10,
}


class PaperConfig(BaseModel):
    paper_starting_balance: float = Field(default=10000.0, gt=0, description="Starting paper balance (USD)")
    paper_position_notional: float = Field(default=10.0, gt=0, description="Position size per trade (USD notional)")
    max_leverage: int = Field(default=10, ge=1, le=125, description="Max leverage")
    risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.05, description="Risk per trade (% of balance)")
    max_open_positions: int = Field(default=3, ge=1, le=10, description="Max concurrent open positions")
    min_signal_confidence: float = Field(default=0.10, ge=0, le=1, description="Min signal confidence to act")


def _load() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return dict(DEFAULTS)
    return dict(DEFAULTS)


def _save(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_paper_config() -> dict:
    """Return current paper config (live values in use by the bot)."""
    return _load()


def update_paper_config(cfg: dict) -> dict:
    """Validate and persist new paper config."""
    validated = PaperConfig(**cfg).model_dump()
    _save(validated)
    return validated


# ── Routes ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/config")
def get_config() -> dict:
    """Return current paper trading configuration."""
    return get_paper_config()


# NOTE: /admin/config POST is overridden by app.api.server (paper-config proxy)
# to accept the SPA field name format.
