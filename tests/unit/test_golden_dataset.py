"""Checks the committed golden dataset under data/golden."""

import io
from pathlib import Path

import pdfplumber
import pytest

from generator.make_case import make_case
from generator.scenarios import build_specs
from triage.golden import GOLDEN_DIR, load_golden_cases

CASES = load_golden_cases()


def test_golden_dataset_has_50_cases():
    assert len(CASES) == 50
    assert sum(case.hard for case in CASES) == 10


def test_every_pdf_has_a_matching_json_and_back():
    for split in ("dev", "holdout"):
        folder = GOLDEN_DIR / split
        pdfs = {path.stem for path in folder.glob("*.pdf")}
        jsons = {path.stem for path in folder.glob("*.json")}
        assert pdfs == jsons, split
        assert pdfs, split


def test_cases_sit_in_the_folder_of_their_split():
    for case in CASES:
        assert (GOLDEN_DIR / case.split / case.pdf_file).is_file(), case.case_id


def test_dev_and_holdout_do_not_overlap():
    dev = {case.case_id for case in CASES if case.split == "dev"}
    holdout = {case.case_id for case in CASES if case.split == "holdout"}
    assert len(dev) == 30
    assert len(holdout) == 20
    assert not dev & holdout


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_committed_pdf_is_readable_text(case):
    path: Path = GOLDEN_DIR / case.split / case.pdf_file
    with pdfplumber.open(io.BytesIO(path.read_bytes())) as pdf:
        text = "".join(page.extract_text() or "" for page in pdf.pages)
    assert "SYNTHETIC TEST DOCUMENT" in text


def test_committed_data_matches_the_generator():
    """Guards against hand edits or generator drift. Faker output is only stable per version."""
    by_id = {case.case_id: case for case in CASES}
    for spec in build_specs():
        generated = make_case(spec)
        assert generated.case == by_id[spec.case_id], spec.case_id
        committed_pdf = (GOLDEN_DIR / spec.split / generated.case.pdf_file).read_bytes()
        assert generated.pdf_bytes == committed_pdf, spec.case_id
