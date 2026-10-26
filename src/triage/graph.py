"""The triage agent as a LangGraph workflow: one state object flows through the nodes.

PDF -> ingest -> redact_pii -> extract -> validate --ok--> classify -> route -> summarize
                                  ^           |
                                  +--retry----+  (at most MAX_RETRIES times)
                                              |
                                        still failing -> human_review
Unreadable PDFs stop after ingest with status "rejected".
"""

import operator
import time
import uuid
from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from triage.llm import LLMProvider, LLMResponse
from triage.nodes.classify import classify
from triage.nodes.extract import extract
from triage.nodes.ingest import UnreadableDocumentError, ingest
from triage.nodes.summarize import summarize
from triage.nodes.validate import ValidationResult, validate
from triage.pii import redact, restore
from triage.rules import RoutingDecision, RoutingPolicy, load_routing_policy, route
from triage.schemas import Category, ExtractionOutput, NodeTrace, Queue, TriageResult

MAX_RETRIES = 2
SUMMARY_SENTENCES = range(3, 6)


class TriageState(TypedDict, total=False):
    request_id: str
    pdf_bytes: bytes
    rejection_reason: str | None
    text: str
    redacted_text: str
    pii_mapping: dict[str, str]
    attempts: int
    extraction: ExtractionOutput | None
    extraction_error: str | None
    errors: list[str]
    validation: ValidationResult | None
    category: Category
    confidence: float
    decision: RoutingDecision
    summary: str
    warnings: list[str]
    prompt_versions: dict[str, str]
    trace: Annotated[list[NodeTrace], operator.add]


def _step(
    node: str, started: float, outcome: str, response: LLMResponse | None = None
) -> list[NodeTrace]:
    return [
        NodeTrace(
            node=node,
            latency_s=round(time.perf_counter() - started, 4),
            prompt_tokens=response.prompt_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            outcome=outcome,
        )
    ]


def build_graph(provider: LLMProvider, policy: RoutingPolicy, today: date | None = None):
    def ingest_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            result = ingest(state["pdf_bytes"])
        except UnreadableDocumentError as error:
            return {
                "rejection_reason": error.reason,
                "trace": _step("ingest", started, f"rejected: {error.reason}"),
            }
        return {
            "text": result.text,
            "rejection_reason": None,
            "trace": _step("ingest", started, f"{result.page_count} pages"),
        }

    def redact_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        redaction = redact(state["text"])
        return {
            "redacted_text": redaction.text,
            "pii_mapping": redaction.mapping,
            "trace": _step("redact_pii", started, f"{len(redaction.mapping)} values redacted"),
        }

    def extract_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        attempt = extract(state["redacted_text"], provider, feedback=state.get("errors"))
        attempts = state.get("attempts", 0) + 1
        update: dict[str, Any] = {
            "attempts": attempts,
            "prompt_versions": {
                **state.get("prompt_versions", {}),
                "extract": attempt.prompt_version,
            },
        }
        update["extraction"] = attempt.output
        update["extraction_error"] = attempt.error
        outcome = "invalid answer" if attempt.output is None else "parsed"
        update["trace"] = _step(
            "extract", started, f"attempt {attempts}: {outcome}", attempt.response
        )
        return update

    def validate_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        if state["extraction"] is None:
            validation, errors = None, [state["extraction_error"]]
        else:
            validation = validate(state["extraction"], state["redacted_text"], today=today)
            errors = validation.errors
        outcome = "ok" if not errors else f"{len(errors)} problems: {'; '.join(errors)}"
        return {
            "validation": validation,
            "errors": errors,
            "trace": _step("validate", started, outcome),
        }

    def after_validate(state: TriageState) -> Literal["ok", "retry", "give_up"]:
        if not state.get("errors"):
            return "ok"
        return "retry" if state["attempts"] <= MAX_RETRIES else "give_up"

    def human_review_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        reason = f"extraction failed validation after {state['attempts']} attempts: " + "; ".join(
            state.get("errors") or []
        )
        return {
            "decision": RoutingDecision(Queue.HUMAN_REVIEW, [reason]),
            "trace": _step("human_review", started, Queue.HUMAN_REVIEW.value),
        }

    def classify_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        result = classify(state["redacted_text"], provider)
        outcome = f"{result.category.value} ({result.confidence:.2f})"
        if result.error:
            outcome += f", {result.error}"
        return {
            "category": result.category,
            "confidence": result.confidence,
            "prompt_versions": {**state["prompt_versions"], "classify": result.prompt_version},
            "trace": _step("classify", started, outcome, result.response),
        }

    def route_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        validation = state["validation"]
        decision = route(
            validation.fields,
            category=state["category"],
            confidence=state["confidence"],
            multiple_claims=validation.multiple_claims,
            missing=validation.missing,
            policy=policy,
        )
        return {"decision": decision, "trace": _step("route", started, decision.queue.value)}

    def summarize_node(state: TriageState) -> dict[str, Any]:
        started = time.perf_counter()
        result = summarize(
            state["redacted_text"],
            state["validation"].fields,
            state["category"],
            state["decision"].queue,
            provider,
        )
        warnings = []
        if result.error:
            warnings.append(f"summary failed: {result.error}")
        elif result.sentence_count not in SUMMARY_SENTENCES:
            warnings.append(f"summary has {result.sentence_count} sentences, expected 3 to 5")
        if result.ungrounded_numbers:
            warnings.append(f"summary numbers not found in the claim: {result.ungrounded_numbers}")
        return {
            "summary": result.summary,
            "warnings": warnings,
            "prompt_versions": {**state["prompt_versions"], "summarize": result.prompt_version},
            "trace": _step("summarize", started, "warnings" if warnings else "ok", result.response),
        }

    graph = StateGraph(TriageState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("redact_pii", redact_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("classify", classify_node)
    graph.add_node("route", route_node)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges(
        "ingest",
        lambda state: "rejected" if state.get("rejection_reason") else "readable",
        {"rejected": END, "readable": "redact_pii"},
    )
    graph.add_edge("redact_pii", "extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges(
        "validate",
        after_validate,
        {"ok": "classify", "retry": "extract", "give_up": "human_review"},
    )
    graph.add_edge("human_review", END)
    graph.add_edge("classify", "route")
    graph.add_edge("route", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def run_triage(
    pdf_bytes: bytes,
    provider: LLMProvider,
    policy: RoutingPolicy | None = None,
    request_id: str | None = None,
    today: date | None = None,
) -> TriageResult:
    request_id = request_id or str(uuid.uuid4())
    app = build_graph(provider, policy or load_routing_policy(), today=today)
    state: TriageState = app.invoke(
        {"request_id": request_id, "pdf_bytes": pdf_bytes, "trace": [], "prompt_versions": {}}
    )
    if state.get("rejection_reason"):
        return TriageResult(
            request_id=request_id,
            status="rejected",
            rejection_reason=state["rejection_reason"],
            trace=state["trace"],
        )

    mapping = state["pii_mapping"]
    validation = state.get("validation")
    fields = validation.fields if validation else None
    if fields and fields.loss_description:
        fields = fields.model_copy(
            update={"loss_description": restore(fields.loss_description, mapping)}
        )
    decision = state["decision"]
    return TriageResult(
        request_id=request_id,
        status="completed",
        queue=decision.queue,
        reasons=decision.reasons,
        category=state.get("category"),
        confidence=state.get("confidence"),
        fields=fields,
        multiple_claims=validation.multiple_claims if validation else False,
        missing_fields=validation.missing if validation else [],
        summary=restore(state["summary"], mapping) if state.get("summary") else None,
        warnings=state.get("warnings", []),
        extraction_attempts=state["attempts"],
        prompt_versions=state["prompt_versions"],
        trace=state["trace"],
    )
