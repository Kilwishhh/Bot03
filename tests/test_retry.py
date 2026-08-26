from app.monitoring.retry import retry_read


def test_retry_read_recovers_from_transient_failure():
    calls = []

    def operation():
        calls.append(True)
        if len(calls) < 2:
            raise TimeoutError("temporary")
        return "ok"

    assert retry_read(operation, attempts=2, delay_seconds=0) == "ok"
    assert len(calls) == 2