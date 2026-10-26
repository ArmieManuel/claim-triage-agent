"""Structured JSON logs and in-memory metrics.

Logs: one JSON object per line on the "triage" logger. Every line of a request carries its
request_id, so `findstr req-42` (or grep) shows the full trace across the nodes.
Privacy: callers log only redacted text, placeholder names and numbers, never document
text or restored values. tests/unit/test_observability.py checks this on a golden case.
"""

import json
import logging
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import UTC, datetime
from typing import Any, TextIO

from triage.schemas import TriageResult

LOGGER_NAME = "triage"
log = logging.getLogger(LOGGER_NAME)

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        line.update({k: v for k, v in vars(record).items() if k not in _STANDARD})
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Send triage logs as JSON lines to stdout. Safe to call more than once."""
    for handler in [h for h in log.handlers if getattr(h, "_triage", False)]:
        log.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._triage = True  # type: ignore[attr-defined]
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False


def _percentile(values: list[float], q: float) -> float | None:
    """Linear interpolation, the same method pandas uses in the evaluation reports."""
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)


class Metrics:
    """Counters plus a sliding window of the latest triage latencies. Thread safe."""

    def __init__(self, window: int = 1000):
        self._lock = threading.Lock()
        self._started = time.time()
        self._http = Counter()
        self._queues = Counter()
        self._categories = Counter()
        self._errors = Counter()
        self._latencies: deque[float] = deque(maxlen=window)
        self._tokens: deque[int] = deque(maxlen=window)
        self._node_latency: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=window)
        )

    def record_http(self, path: str, status: int, latency_s: float) -> None:
        with self._lock:
            self._http[str(status)] += 1

    def record_triage(self, result: TriageResult, latency_s: float) -> None:
        with self._lock:
            self._queues[result.queue.value if result.queue else "none"] += 1
            if result.category:
                self._categories[result.category.value] += 1
            self._latencies.append(latency_s)
            self._tokens.append(sum(s.prompt_tokens + s.output_tokens for s in result.trace))
            for step in result.trace:
                self._node_latency[step.node].append(step.latency_s)

    def record_triage_error(self, code: str) -> None:
        with self._lock:
            self._errors[code] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            completed = sum(self._queues.values())
            errors = sum(self._errors.values())
            requests = completed + errors
            latencies = list(self._latencies)
            return {
                "uptime_s": round(time.time() - self._started, 1),
                "http_requests_total": sum(self._http.values()),
                "http_by_status": dict(self._http),
                "triage": {
                    "requests": requests,
                    "completed": completed,
                    "errors_by_code": dict(self._errors),
                    "error_rate": round(errors / requests, 4) if requests else 0.0,
                    "by_queue": dict(self._queues),
                    "by_category": dict(self._categories),
                    "latency_p50_s": _percentile(latencies, 0.5),
                    "latency_p95_s": _percentile(latencies, 0.95),
                    "tokens_mean": round(sum(self._tokens) / len(self._tokens), 1)
                    if self._tokens
                    else None,
                    "node_latency_mean_s": {
                        node: round(sum(values) / len(values), 3)
                        for node, values in self._node_latency.items()
                        if values
                    },
                },
            }
