from app.runtime import BotRunner


class FakeCycle:
    def __init__(self):
        self.calls = 0

    def run_once(self, symbol, timeframe):
        self.calls += 1


def test_bot_runner_runs_requested_cycles():
    cycle = FakeCycle()
    assert BotRunner(cycle, "BTCUSDT", "15m", 0.001).run(max_cycles=2) == 2
    assert cycle.calls == 2
