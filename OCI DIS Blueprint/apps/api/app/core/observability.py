"""Low-cardinality structured request telemetry for local and OCI runtimes."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)
logger = logging.getLogger("oci_dis.request")
logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.propagate = False


class RequestTelemetryMiddleware(BaseHTTPMiddleware):
    """Emit one sanitized JSON event and propagate a correlation identifier."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())
        incoming_traceparent = request.headers.get("traceparent", "").lower()
        trace_match = _TRACEPARENT.fullmatch(incoming_traceparent)
        if trace_match and trace_match.group("trace_id") != "0" * 32:
            trace_id = trace_match.group("trace_id")
            trace_flags = trace_match.group("flags")
        else:
            trace_id = uuid.uuid4().hex
            trace_flags = "01"
        traceparent = f"00-{trace_id}-{uuid.uuid4().hex[:16]}-{trace_flags}"
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        started = time.perf_counter()
        status_code = 500
        error_type: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            response.headers["traceparent"] = traceparent
            return response
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            route = request.scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            event: dict[str, object] = {
                "event": "http_request",
                "request_id": request_id,
                "trace_id": trace_id,
                "method": request.method,
                "route": route_template,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            if error_type:
                event["error_type"] = error_type
            logger.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
