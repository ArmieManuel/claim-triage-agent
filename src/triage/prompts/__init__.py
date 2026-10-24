"""Versioned prompt files. Each evaluation report records the versions it used."""

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

import yaml

PROMPT_DIR = Path(__file__).parent


class PromptError(ValueError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    def render(self, **values: str) -> str:
        needed = {field for _, field, _, _ in Formatter().parse(self.user) if field}
        missing = needed - values.keys()
        if missing:
            raise PromptError(f"prompt {self.name} is missing values for {sorted(missing)}")
        return self.user.format(**values)


def load_prompt(name: str) -> Prompt:
    raw = yaml.safe_load((PROMPT_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    return Prompt(name=name, version=raw["version"], system=raw["system"], user=raw["user"])
