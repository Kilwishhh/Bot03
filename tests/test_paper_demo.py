from scripts.run_paper_demo import build_demo_candles


def test_demo_data_is_sufficient_for_strategy():
    assert len(build_demo_candles()) == 11
