"""Loading the golden dataset from data/golden."""

from pathlib import Path

from triage.schemas import GoldenCase

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"


def load_golden_cases(root: Path = GOLDEN_DIR, split: str | None = None) -> list[GoldenCase]:
    splits = [split] if split else ["dev", "holdout"]
    cases = []
    for name in splits:
        for path in sorted((root / name).glob("*.json")):
            cases.append(GoldenCase.model_validate_json(path.read_text(encoding="utf-8")))
    return cases
