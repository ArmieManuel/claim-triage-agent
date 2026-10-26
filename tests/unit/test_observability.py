import io
import json
import logging
import re
from contextlib import contextmanager
from datetime import date

import pytest

from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.graph import run_triage
from triage.llm import FakeProvider
from triage.observability import LOGGER_NAME, JsonFormatter, Metrics, configure_logging
from triage.schemas import NodeTrace, Queue, TriageResult

CASE = next(c for c in load_golden_cases(split="dev") if c.case_id == "case_013")
PIPELINE = ["ingest", "redact_pii", "extract", "validate", "classify", "route", "summarize"]


@contextmanager
def captured():
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    lines: list[dict] = []
    try:
        yield lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        lines.extend(json.loads(line) for line in buffer.getvalue().splitlines())


def scripted(system, prompt, schema):
    props = schema["properties"]
    if "multiple_claims" in props:
        data = json.loads(CASE.expected.fields.model_dump_json())
        return json.dumps({**data, "multiple_claims": False})
    if "confidence" in props:
        return json.dumps(
            {"category": "other", "alternative_category": None, "confidence": 0.9, "reason": "x"}
        )
    return json.dumps({"summary": "Claim filed by [NAME_1]. It was routed. Done."})


def triage_with_logs():
    with captured() as lines:
        result = run_triage(
            (GOLDEN_DIR / "dev" / CASE.pdf_file).read_bytes(),
            FakeProvider(scripted),
            request_id="req-42",
            today=date(2026, 10, 27),
        )
    return result, lines


def test_formatter_writes_one_json_object_with_the_extra_fields():
    record = logging.LogRecord(LOGGER_NAME, logging.INFO, __file__, 1, "node_completed", None, None)
    record.request_id, record.node, record.latency_s = "r1", "extract", 1.25
    line = json.loads(JsonFormatter().format(record))
    assert line["event"] == "node_completed"
    assert line["level"] == "INFO"
    assert (line["request_id"], line["node"], line["latency_s"]) == ("r1", "extract", 1.25)
    assert re.match(r"\d{4}-\d{2}-\d{2}T", line["ts"])


def test_configure_logging_does_not_add_duplicate_handlers():
    stream = io.StringIO()
    configure_logging(stream=stream)
    configure_logging(stream=stream)
    marked = [h for h in logging.getLogger(LOGGER_NAME).handlers if getattr(h, "_triage", False)]
    assert len(marked) == 1


def test_one_request_logs_a_trace_across_all_nodes():
    result, lines = triage_with_logs()
    nodes = [line for line in lines if line["event"] == "node_completed"]
    assert [line["node"] for line in nodes] == PIPELINE
    assert {line["request_id"] for line in lines} == {"req-42"}
    extract = next(line for line in nodes if line["node"] == "extract")
    assert extract["prompt_tokens"] > 0
    assert extract["latency_s"] >= 0
    assert "outcome" in extract
    done = lines[-1]
    assert done["event"] == "triage_completed"
    assert done["queue"] == result.queue.value
    assert done["total_tokens"] > 0


def test_logs_contain_placeholders_never_personal_data():
    _, lines = triage_with_logs()
    text = re.sub(r"\s+", " ", json.dumps(lines, ensure_ascii=False))
    for pii in CASE.pii:
        assert re.sub(r"\s+", " ", pii.value) not in text, pii.kind
    assert "[NAME_1]" in text  # the redacted summary is logged, with placeholders


def result(queue: Queue, tokens: int = 100) -> TriageResult:
    return TriageResult(
        request_id="r",
        status="completed",
        queue=queue,
        trace=[
            NodeTrace(node="extract", latency_s=2.0, prompt_tokens=tokens, outcome="ok"),
            NodeTrace(node="route", latency_s=0.0, outcome="ok"),
        ],
    )


def test_metrics_summarize_requests_latency_and_errors():
    m = Metrics()
    m.record_http("/v1/triage", 200, 10.0)
    m.record_http("/v1/triage", 200, 30.0)
    m.record_http("/v1/triage", 415, 0.1)
    m.record_http("/health", 200, 0.01)
    m.record_triage(result(Queue.AUTO_PROCESS), 10.0)
    m.record_triage(result(Queue.HUMAN_REVIEW, tokens=300), 30.0)
    m.record_triage_error("unsupported_media_type")
    snap = m.snapshot()
    assert snap["http_requests_total"] == 4
    assert snap["http_by_status"] == {"200": 3, "415": 1}
    t = snap["triage"]
    assert t["requests"] == 3
    assert t["completed"] == 2
    assert t["errors_by_code"] == {"unsupported_media_type": 1}
    assert t["error_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert t["by_queue"] == {"auto_process": 1, "human_review": 1}
    assert t["latency_p50_s"] == 20.0
    assert t["latency_p95_s"] == pytest.approx(29.0)
    assert t["tokens_mean"] == 200
    assert t["node_latency_mean_s"]["extract"] == 2.0


def test_empty_metrics_do_not_crash():
    t = Metrics().snapshot()["triage"]
    assert t["requests"] == 0
    assert t["latency_p50_s"] is None
    assert t["error_rate"] == 0.0
