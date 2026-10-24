"""Step 7: a 3 to 5 sentence summary for the handler, with a check for invented numbers."""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, ValidationError

from triage.llm import LLMProvider, LLMResponse
from triage.prompts import load_prompt
from triage.schemas import Category, ClaimFields, Queue


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str


@dataclass(frozen=True)
class SummarizeResult:
    summary: str
    sentence_count: int
    ungrounded_numbers: list[str] = field(default_factory=list)
    error: str | None = None
    response: LLMResponse | None = None
    prompt_version: str = ""


def count_sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def ungrounded_numbers(summary: str, source: str) -> list[str]:
    """Numbers of two or more digits in the summary that appear nowhere in the source."""
    squashed = re.sub(r"[\s,]", "", source)
    numbers = (n.replace(",", "") for n in re.findall(r"\d[\d,.]*\d", summary))
    return [n for n in dict.fromkeys(numbers) if n.removesuffix(".00") not in squashed]


def summarize(
    document: str,
    fields: ClaimFields,
    category: Category,
    queue: Queue,
    provider: LLMProvider,
) -> SummarizeResult:
    prompt = load_prompt("summarize")
    fields_json = fields.model_dump_json(exclude_none=True, indent=2)
    response = provider.generate(
        system=prompt.system,
        prompt=prompt.render(
            document=document, fields=fields_json, category=category.value, queue=queue.value
        ),
        schema=SummaryOutput.model_json_schema(),
    )
    try:
        summary = SummaryOutput.model_validate_json(response.content).summary.strip()
    except ValidationError as error:
        return SummarizeResult(
            "",
            0,
            error=f"the answer did not match the JSON schema ({error.error_count()} problems)",
            response=response,
            prompt_version=prompt.version,
        )
    return SummarizeResult(
        summary=summary,
        sentence_count=count_sentences(summary),
        ungrounded_numbers=ungrounded_numbers(summary, document + fields_json),
        response=response,
        prompt_version=prompt.version,
    )
