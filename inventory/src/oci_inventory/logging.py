from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LogConfig:
    level: str = "INFO"
    json_logs: bool = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat(timespec="milliseconds")
            + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Include extra fields if present
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            ):
                if value is None:
                    continue
                try:
                    json.dumps({key: value})
                    payload[key] = value
                except Exception:
                    # skip non-serializable extras
                    pass
        return json.dumps(payload, sort_keys=True)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        timestamp = datetime.utcfromtimestamp(record.created).isoformat(timespec="seconds") + "Z"
        step = getattr(record, "step", None)
        phase = getattr(record, "phase", None)
        message = record.getMessage()
        if step or phase:
            step_label = step if step else "unknown"
            phase_label = phase if phase else "unknown"
            message = f"[{step_label}:{phase_label}] {message}"
        return f"{timestamp} {record.levelname} {record.name}: {message}"


def _level_from_str(level: str) -> int:
    try:
        return getattr(logging, level.upper())
    except Exception:
        return logging.INFO


def setup_logging(config: Optional[LogConfig] = None) -> None:
    """
    Configure root logger once. Subsequent calls are no-ops.
    Env overrides:
      - OCI_INV_LOG_LEVEL (default INFO)
      - OCI_INV_JSON_LOGS (1/true to enable)
    """
    if getattr(setup_logging, "_configured", False):
        return

    env_level = os.getenv("OCI_INV_LOG_LEVEL")
    env_json = os.getenv("OCI_INV_JSON_LOGS")

    level = _level_from_str((config.level if config else None) or env_level or "INFO")
    json_logs = (config.json_logs if config else False) or (
        (env_json or "").lower() in ("1", "true", "yes")
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(PlainFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if running under certain test runners
    root.handlers = [handler]

    # Reduce noise from 3rd-party libraries unless explicitly raised
    logging.getLogger("oci").setLevel(max(level, logging.WARNING))
    logging.getLogger("botocore").setLevel(max(level, logging.WARNING))

    setattr(setup_logging, "_configured", True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
