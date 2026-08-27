from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter()

# Metrics exported for observability (Phase 4)
TRADE_CYCLES_TOTAL = Counter("mktrader_cycles_total", "Total trading cycles executed", ["status"])
TRADE_SIGNALS_TOTAL = Counter("mktrader_signals_total", "Total signals generated", ["side"])
TRADE_ORDERS_TOTAL = Counter("mktrader_orders_total", "Total orders submitted", ["status"])
TRADE_ERRORS_TOTAL = Counter("mktrader_errors_total", "Total errors recorded", ["error_type"])
CYCLE_DURATION_SECONDS = Histogram("mktrader_cycle_duration_seconds", "Duration of a trading cycle")
BOT_RUNNING = Gauge("mktrader_bot_running", "Whether the bot is currently running")
BALANCE_USDT = Gauge("mktrader_balance_usdt", "Available USDT balance")
OPEN_POSITIONS = Gauge("mktrader_open_positions", "Number of open positions")


def record_cycle(status: str, duration_seconds: float) -> None:
    TRADE_CYCLES_TOTAL.labels(status=status).inc()
    CYCLE_DURATION_SECONDS.observe(duration_seconds)


def record_signal(side: str) -> None:
    TRADE_SIGNALS_TOTAL.labels(side=side).inc()


def record_order(status: str) -> None:
    TRADE_ORDERS_TOTAL.labels(status=status).inc()


def record_error(error_type: str) -> None:
    TRADE_ERRORS_TOTAL.labels(error_type=error_type).inc()


@router.get("/metrics")
def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
