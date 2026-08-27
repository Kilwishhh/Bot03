from app.monitoring.logger import redact_secrets


def test_logger_redacts_credentials():
    message = "api_key=abc123 api_secret:xyz bot_token=token private_key=secret"
    redacted = redact_secrets(message)
    assert "abc123" not in redacted
    assert "xyz" not in redacted
    assert "bot_token=token" not in redacted
    assert "private_key=secret" not in redacted
    assert "[REDACTED]" in redacted
