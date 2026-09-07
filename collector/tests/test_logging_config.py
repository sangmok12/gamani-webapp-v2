import json
import logging

from gamani_collector.logging_config import JsonFormatter


def test_json_formatter_includes_structured_fields() -> None:
    record = logging.LogRecord(
        name="gamani_collector.http_client",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.event = "http_request_completed"
    record.path = "/v1/test"
    record.status_code = 200
    record.attempt = 1
    record.elapsed_ms = 25

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "http_request_completed"
    assert payload["path"] == "/v1/test"
    assert payload["status_code"] == 200
    assert payload["attempt"] == 1
    assert payload["elapsed_ms"] == 25


def test_json_formatter_does_not_include_unapproved_fields() -> None:
    record = logging.LogRecord(
        name="gamani_collector.http_client",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.response_body = {"vehicleNo": "SECRET"}
    record.database_url = "postgresql://user:password@localhost/database"

    formatted = JsonFormatter().format(record)

    assert "SECRET" not in formatted
    assert "password" not in formatted
