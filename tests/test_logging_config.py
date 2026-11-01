"""Console timestamps include milliseconds and a local UTC offset."""

import logging
import re

from app.core.logging_config import LocalTimeFormatter


def test_local_log_timestamp_has_timezone() -> None:
    record = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, "request start", (), None)
    formatted = LocalTimeFormatter("%(asctime)s %(levelname)s %(message)s").format(record)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2} INFO request start$", formatted)
