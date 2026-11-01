"""Console log timestamps in local time with an explicit UTC offset."""

import logging
from datetime import datetime, timezone


class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        local_time = datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone()
        return local_time.isoformat(timespec="milliseconds")


def timestamp_uvicorn_handlers() -> None:
    """Also format request logs when launched without --log-config."""
    formatter = LocalTimeFormatter("%(asctime)s %(levelname)-5s %(process)d %(name)s: %(message)s")
    for handler in logging.getLogger("uvicorn").handlers:
        handler.setFormatter(formatter)
