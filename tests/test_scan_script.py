from scripts.scan_binance_futures import main


def test_scan_script_is_importable(monkeypatch, capsys):
    class FakeExchange:
        def get_symbols(self):
            return []

    monkeypatch.setattr("scripts.scan_binance_futures.BinanceFuturesAdapter", lambda *args, **kwargs: FakeExchange())
    monkeypatch.setattr("scripts.scan_binance_futures.Settings", lambda **kwargs: type("Settings", (), {"timeframe": "15m", "enable_telegram": False})())
    monkeypatch.setattr("scripts.scan_binance_futures.argparse.ArgumentParser.parse_args", lambda self: type("Args", (), {"timeframe": None, "limit": 100, "max_symbols": None})())
    class FakeScanner:
        def __init__(self, *args):
            pass

        def scan(self, timeframe, limit=100, symbols=None):
            return []
    monkeypatch.setattr("scripts.scan_binance_futures.FuturesSignalScanner", FakeScanner)
    main()
    assert "scanned_symbols=0" in capsys.readouterr().out