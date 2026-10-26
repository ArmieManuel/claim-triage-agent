import json

from triage.cli import main
from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.llm import FakeProvider

CASE = next(c for c in load_golden_cases(split="dev") if c.case_id == "case_013")


def scripted(system, prompt, schema):
    props = schema["properties"]
    if "multiple_claims" in props:
        data = json.loads(CASE.expected.fields.model_dump_json())
        return json.dumps({**data, "multiple_claims": False})
    if "confidence" in props:
        return json.dumps({"category": "other", "confidence": 0.9, "reason": "Fits."})
    return json.dumps({"summary": "One. Two. Three."})


def test_cli_prints_a_readable_result(capsys):
    path = GOLDEN_DIR / "dev" / CASE.pdf_file
    assert main([str(path)], provider=FakeProvider(scripted)) == 0
    out = capsys.readouterr().out
    assert "standard_handler" in out
    assert "CLM-2026-35152" in out
    assert "One. Two. Three." in out


def test_cli_can_print_json(capsys):
    path = GOLDEN_DIR / "dev" / CASE.pdf_file
    main([str(path), "--json"], provider=FakeProvider(scripted))
    result = json.loads(capsys.readouterr().out)
    assert result["queue"] == "standard_handler"
    assert result["status"] == "completed"


def test_cli_reports_rejected_files(tmp_path, capsys):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    assert main([str(bad)], provider=FakeProvider([])) == 2
    assert "rejected" in capsys.readouterr().out
