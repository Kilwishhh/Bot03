"""Structured application logging."""

import logging
import re


_SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|api[_-]?secret|bot[_-]?token|private[_-]?key|seed[_-]?phrase|project[_-]?id)(\s*[=:]\s*)[^\s,;]+")


def redact_secrets(message: str) -> str:
    """Remove common credential values before they reach a log sink."""
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", message)


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(str(record.msg))
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactionFilter())
