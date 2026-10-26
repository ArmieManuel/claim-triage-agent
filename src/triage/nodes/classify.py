"""Step 5: classify the claim. A bad answer becomes confidence 0, which routes to human review.

The model's own confidence is unreliable on ambiguous claims (baseline case_030: 0.95 on a
water-or-fire claim). So the model is also asked for a second category that fits, and naming
one caps the confidence below the human review threshold. The decision stays in code.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from triage.llm import LLMProvider, LLMResponse
from triage.prompts import load_prompt
from triage.schemas import Category

AMBIGUOUS_CONFIDENCE = 0.5


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    alternative_category: Category | None = Field(
        description="A second category that also clearly fits, or null"
    )
    confidence: float = Field(ge=0, le=1)
    reason: str


@dataclass(frozen=True)
class ClassifyResult:
    category: Category
    confidence: float
    reason: str
    error: str | None
    response: LLMResponse
    prompt_version: str
    alternative_category: Category | None = None


def classify(document: str, provider: LLMProvider) -> ClassifyResult:
    prompt = load_prompt("classify")
    response = provider.generate(
        system=prompt.system,
        prompt=prompt.render(document=document),
        schema=ClassificationOutput.model_json_schema(),
    )
    try:
        output = ClassificationOutput.model_validate_json(response.content)
    except ValidationError as error:
        return ClassifyResult(
            Category.OTHER,
            0.0,
            "",
            f"the answer did not match the JSON schema ({error.error_count()} problems)",
            response,
            prompt.version,
        )
    alternative = output.alternative_category
    if alternative == output.category:
        alternative = None
    confidence = min(output.confidence, AMBIGUOUS_CONFIDENCE) if alternative else output.confidence
    return ClassifyResult(
        output.category, confidence, output.reason, None, response, prompt.version, alternative
    )
