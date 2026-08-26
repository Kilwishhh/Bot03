from app.dashboard.streamlit_app import load_counts
from app.database import TradingRepository


def test_dashboard_reads_repository_counts(tmp_path):
    repository = TradingRepository(tmp_path / "dashboard.sqlite3")
    repository.close()
    assert load_counts(tmp_path / "dashboard.sqlite3") == {"signals": 0, "orders": 0, "trades": 0, "daily_pnl": 0, "bot_events": 0, "errors": 0, "balances": 0, "positions": 0}