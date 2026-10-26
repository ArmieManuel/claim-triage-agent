import json
from datetime import date

import pytest

from triage.llm import FakeProvider
from triage.nodes.classify import AMBIGUOUS_CONFIDENCE, ClassificationOutput, classify
from triage.nodes.summarize import SummaryOutput, summarize
from triage.schemas import Category, ClaimFields, Queue

DOC = "Claim CLM-2026-35152. A pipe burst in Hamburg on 2026-05-09. Amount claimed EUR 3627.55."
FIELDS = ClaimFields(
    claim_number="CLM-2026-35152",
    date_of_loss=date(2026, 5, 9),
    amount_claimed=3627.55,
    location="Hamburg",
)


def answer(**values) -> str:
    return json.dumps(values)


# classify


def classification(**values) -> str:
    return answer(**{"alternative_category": None, "reason": "Fits.", **values})


def test_classify_parses_category_and_confidence():
    fake = FakeProvider([classification(category="property_water", confidence=0.93)])
    result = classify(DOC, fake)
    assert result.category == Category.PROPERTY_WATER
    assert result.confidence == 0.93
    assert result.alternative_category is None
    assert result.error is None
    assert result.prompt_version == "classify-v2"
    assert fake.calls[0]["schema"] == ClassificationOutput.model_json_schema()
    assert DOC in fake.calls[0]["prompt"]


def test_a_second_fitting_category_caps_confidence():
    """The model's own confidence is unreliable on ambiguous claims (case_030 in the baseline),
    so naming a second category caps confidence below the human review threshold."""
    fake = FakeProvider(
        [
            classification(
                category="property_fire", alternative_category="property_water", confidence=0.95
            )
        ]
    )
    result = classify(DOC, fake)
    assert result.category == Category.PROPERTY_FIRE
    assert result.alternative_category == Category.PROPERTY_WATER
    assert result.confidence == AMBIGUOUS_CONFIDENCE < 0.7


def test_an_alternative_equal_to_the_category_is_ignored():
    fake = FakeProvider(
        [classification(category="other", alternative_category="other", confidence=0.9)]
    )
    result = classify(DOC, fake)
    assert result.confidence == 0.9
    assert result.alternative_category is None


@pytest.mark.parametrize(
    "bad",
    [
        "nonsense",
        answer(category="boat_sinking", confidence=0.9, reason="x"),
        answer(category="other", confidence=1.7, reason="x"),
    ],
)
def test_classify_falls_back_to_zero_confidence_on_bad_answers(bad):
    result = classify(DOC, FakeProvider([bad]))
    assert result.category == Category.OTHER
    assert result.confidence == 0.0
    assert result.error


# summarize


GOOD_SUMMARY = (
    "A pipe burst in Hamburg on 2026-05-09. The claimant asks for EUR 3,627.55. "
    "Claim CLM-2026-35152 was routed to the standard handler."
)


def test_summarize_returns_the_summary_and_sends_context():
    fake = FakeProvider([answer(summary=GOOD_SUMMARY)])
    result = summarize(DOC, FIELDS, Category.PROPERTY_WATER, Queue.STANDARD_HANDLER, fake)
    assert result.summary == GOOD_SUMMARY
    assert result.sentence_count == 3
    assert result.ungrounded_numbers == []
    assert result.prompt_version == "summarize-v1"
    prompt = fake.calls[0]["prompt"]
    assert DOC in prompt
    assert "standard_handler" in prompt
    assert "CLM-2026-35152" in prompt
    assert fake.calls[0]["schema"] == SummaryOutput.model_json_schema()


def test_summarize_flags_numbers_that_are_not_in_the_source():
    invented = GOOD_SUMMARY + " A second payment of EUR 9,999 was already made."
    fake = FakeProvider([answer(summary=invented)])
    result = summarize(DOC, FIELDS, Category.PROPERTY_WATER, Queue.STANDARD_HANDLER, fake)
    assert result.ungrounded_numbers == ["9999"]


def test_summarize_reports_bad_answers():
    result = summarize(DOC, FIELDS, Category.OTHER, Queue.HUMAN_REVIEW, FakeProvider(["{}"]))
    assert result.summary == ""
    assert result.error
