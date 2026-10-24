import pytest

from triage.prompts import PROMPT_DIR, PromptError, load_prompt

NAMES = ("extract", "classify", "summarize")


@pytest.mark.parametrize("name", NAMES)
def test_prompts_have_a_version_system_text_and_document_slot(name):
    prompt = load_prompt(name)
    assert prompt.version.startswith(f"{name}-v")
    assert prompt.system.strip()
    assert "{document}" in prompt.user


def test_render_fills_placeholders():
    prompt = load_prompt("extract")
    text = prompt.render(document="CLAIM TEXT", feedback="")
    assert "CLAIM TEXT" in text
    assert "{" not in text


def test_render_refuses_missing_placeholders():
    with pytest.raises(PromptError):
        load_prompt("extract").render(document="x")


def test_prompt_versions_are_unique():
    versions = [load_prompt(path.stem).version for path in PROMPT_DIR.glob("*.yaml")]
    assert len(versions) == len(set(versions))
