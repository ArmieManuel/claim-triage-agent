"""Step 5: classify the claim. A bad answer becomes confidence 0, which routes to human review."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from triage.llm import LLMProvider, LLMResponse
from triage.prompts import load_prompt
from triage.schemas import Category


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
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
    return ClassifyResult(
        output.category, output.confidence, output.reason, None, response, prompt.version
    )
