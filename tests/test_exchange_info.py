from app.exchange.paper import PaperTradingAdapter


def test_paper_exchange_info_has_precision_rules():
    info = PaperTradingAdapter().get_exchange_info("BTCUSDT")
    assert info["step_size"] == "0.001"
    assert info["tick_size"] == "0.01"