"""Three-layer error handling adhering to Burns Lab design principles.

Provides a unified error format serving three audiences simultaneously:
1. Human message: clear statement of what happened for the human user.
2. LLM guidance: actionable instructions for the calling agent (is it retryable, what to do next).
3. Diagnostic trace: error_type, sanitized detail, trace_id, timestamp, and optional traceback.
"""

from __future__ import annotations

import json
import re
import secrets
import traceback
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Detroit")

_SENSITIVE_PATTERNS = [
    (re.compile(r"(password\s*=\s*['\"]?)([^&\s'\"]+)(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\3"),
    (re.compile(r"(://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1[REDACTED]\3"),
    (re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token\s*=\s*['\"]?)([a-zA-Z0-9_\-\.]+)(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\3"),
    (re.compile(r"(secret\s*=\s*['\"]?)([a-zA-Z0-9_\-\.]+)(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\3"),
]


def sanitize_text(text: str) -> str:
    """Mask credentials, passwords, and tokens from diagnostic strings."""
    if not text:
        return ""
    sanitized = text
    for pattern, repl in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(repl, sanitized)
    return sanitized


class McpServiceError(Exception):
    """Exception carrying Burns Lab three-layer error payload."""

    def __init__(
        self,
        error: str,
        guidance: str,
        retryable: bool = False,
        error_type: str | None = None,
        detail: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(error)
        self.error = error
        self.guidance = guidance
        self.retryable = retryable
        self.error_type = error_type or self.__class__.__name__
        self.detail = detail or error
        self.trace_id = trace_id or f"err_{secrets.token_hex(4)}"
        self.timestamp = datetime.now(LOCAL_TZ).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error": sanitize_text(self.error),
            "guidance": {
                "retryable": self.retryable,
                "next_action": sanitize_text(self.guidance),
            },
            "diagnostic": {
                "error_type": self.error_type,
                "detail": sanitize_text(self.detail),
                "trace_id": self.trace_id,
                "timestamp": self.timestamp,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def format_three_layer_error(
    error: str,
    next_action: str,
    *,
    retryable: bool = False,
    exc: Exception | None = None,
    error_type: str | None = None,
    detail: str | None = None,
    trace_id: str | None = None,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """Build a three-layer error dictionary conforming to Burns Lab standards."""
    tid = trace_id or f"err_{secrets.token_hex(4)}"
    etype = error_type or (exc.__class__.__name__ if exc else "ServiceError")
    det = detail or (str(exc) if exc else error)

    diagnostic: dict[str, Any] = {
        "error_type": etype,
        "detail": sanitize_text(det),
        "trace_id": tid,
        "timestamp": datetime.now(LOCAL_TZ).isoformat(),
    }
    if include_traceback and exc:
        diagnostic["traceback"] = sanitize_text("".join(traceback.format_exception(exc)))

    return {
        "status": "error",
        "error": sanitize_text(error),
        "guidance": {
            "retryable": retryable,
            "next_action": sanitize_text(next_action),
        },
        "diagnostic": diagnostic,
    }


def format_three_layer_error_json(
    error: str,
    next_action: str,
    *,
    retryable: bool = False,
    exc: Exception | None = None,
    error_type: str | None = None,
    detail: str | None = None,
    trace_id: str | None = None,
    include_traceback: bool = False,
) -> str:
    """Build and JSON-serialize a three-layer error conforming to Burns Lab standards."""
    data = format_three_layer_error(
        error,
        next_action,
        retryable=retryable,
        exc=exc,
        error_type=error_type,
        detail=detail,
        trace_id=trace_id,
        include_traceback=include_traceback,
    )
    return json.dumps(data, default=str)
