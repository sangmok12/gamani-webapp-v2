import json
import logging
from datetime import UTC, datetime

LOG_FIELDS = (
    "event",
    "path",
    "status_code",
    "attempt",
    "elapsed_ms",
    "retry_delay_seconds",
    "error_type",
)


class JsonFormatter(logging.Formatter):
    """Format application logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in LOG_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the logger used by the collector."""

    logger = logging.getLogger("gamani_collector")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
