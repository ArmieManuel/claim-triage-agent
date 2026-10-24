"""Step 3: ask the model to fill the extraction schema from the redacted document."""

from dataclasses import dataclass

from pydantic import ValidationError

from triage.llm import LLMProvider, LLMResponse
from triage.prompts import load_prompt
from triage.schemas import ExtractionOutput


@dataclass(frozen=True)
class ExtractAttempt:
    output: ExtractionOutput | None
    error: str | None
    response: LLMResponse
    prompt_version: str


def feedback_text(problems: list[str] | None) -> str:
    if not problems:
        return ""
    lines = "\n".join(f"- {problem}" for problem in problems)
    return f"Your previous answer had these problems. Fix them and answer again:\n{lines}"


def extract(
    document: str, provider: LLMProvider, feedback: list[str] | None = None
) -> ExtractAttempt:
    prompt = load_prompt("extract")
    response = provider.generate(
        system=prompt.system,
        prompt=prompt.render(document=document, feedback=feedback_text(feedback)),
        schema=ExtractionOutput.model_json_schema(),
    )
    try:
        output = ExtractionOutput.model_validate_json(response.content)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'answer'}: {e['msg']}"
            for e in error.errors()[:5]
        )
        return ExtractAttempt(
            None, f"the answer did not match the JSON schema ({problems})", response, prompt.version
        )
    return ExtractAttempt(output, None, response, prompt.version)
