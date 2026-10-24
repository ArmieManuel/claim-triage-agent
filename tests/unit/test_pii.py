import re

import pytest

from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.nodes.ingest import ingest
from triage.pii import redact, restore


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize(
    ("text", "secret", "kind"),
    [
        ("Email tadeusz17@example.org", "tadeusz17@example.org", "EMAIL"),
        ("Phone 03020 175270", "03020 175270", "PHONE"),
        ("Contact number (05042) 288667", "(05042) 288667", "PHONE"),
        ("Telephone +43 3528 34971 449", "+43 3528 34971 449", "PHONE"),
        ("call +49(0) 642621299 today", "+49(0) 642621299", "PHONE"),
        ("Phone +49 (0) 9765 440909", "+49 (0) 9765 440909", "PHONE"),
        ("Phone +43 (0) 1 33289782", "+43 (0) 1 33289782", "PHONE"),
        ("Phone 03845/27455495", "03845/27455495", "PHONE"),
        ("the codice fiscale is STNCLD05L60A201E.", "STNCLD05L60A201E", "ID"),
        ("the German tax ID is 91658148058.", "91658148058", "ID"),
        ("SV number 9452180111", "9452180111", "ID"),
        ("IBAN DE08 1454 7527 7204 0560 86", "DE08 1454 7527 7204 0560 86", "IBAN"),
        ("The vehicle registration is MZG-W-37.", "MZG-W-37", "PLATE"),
        ("Reg. number GR-1 GYG", "GR-1 GYG", "PLATE"),
    ],
)
def test_redact_finds_pattern_based_pii(text, secret, kind):
    result = redact(text)
    assert secret not in result.text
    assert f"[{kind}_1]" in result.text


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Claimant name Renate Naser\nPhone 03020 175270", "Renate Naser"),
        (
            "From: Dr. Sylvie Kaul MBA. <x@example.net>\nTo: claims@a.example",
            "Dr. Sylvie Kaul MBA.",
        ),
        ("Thanks,\nTherese Pöschl\n+43 5276 98317 022", "Therese Pöschl"),
        ("Yours faithfully,\nGiacinto Emo", "Giacinto Emo"),
        (
            "I am writing on behalf of my client, Luciano Missoni, who holds the policy.",
            "Luciano Missoni",
        ),
        ("a claim against your policyholder, Anna\nBerger.\nThe roof tile fell.", "Anna Berger"),
    ],
)
def test_redact_finds_names_from_context(text, name):
    result = redact(text)
    assert name not in flat(result.text)
    assert "[NAME_1]" in result.text


def test_a_found_name_is_replaced_everywhere_even_across_line_breaks():
    text = "Giacinto Emo\nVicolo Calvo, 140\nDear Sir,\nI, Giacinto\nEmo, write.\nYours faithfully,\nGiacinto Emo"
    result = redact(text)
    assert "Giacinto" not in result.text
    assert result.text.count("[NAME_1]") == 3


@pytest.mark.parametrize(
    ("text", "address"),
    [
        (
            "Home address Fridolin-Reinisch-Gasse 35, 6314 Mattighofen\nPhone 1",
            "Fridolin-Reinisch-Gasse 35, 6314 Mattighofen",
        ),
        (
            "Name X Y\nVicolo Calvo, 140\n36075, Montecchio Maggiore (VI)\n",
            "Vicolo Calvo, 140 36075, Montecchio Maggiore (VI)",
        ),
        (
            "+43 5276 98317 022\nKatharina-Lehner-Straße 7/6, 5892 Mureck\n",
            "Katharina-Lehner-Straße 7/6, 5892 Mureck",
        ),
    ],
)
def test_redact_finds_addresses(text, address):
    result = redact(text)
    assert address not in flat(result.text)
    assert "[ADDRESS_1]" in result.text


@pytest.mark.parametrize(
    "keep",
    [
        "CLM-2026-35152",
        "POL-78952443",
        "AL/721103/GN",
        "DG-6412-6260",
        "AT/48213/25",
        "16.08.2025",
        "03/03/2026",
        "2026-05-09",
        "€18,073.85",
        "EUR 3627.55",
        "83,302.00 euros",
        "Hamburg",
    ],
)
def test_redact_keeps_claim_data(keep):
    text = f"Claim details\nValue {keep}\nThe incident happened in Turin."
    assert keep in redact(text).text


def test_same_value_gets_the_same_placeholder():
    result = redact("Email a@example.com and again a@example.com, also b@example.com")
    assert result.text.count("[EMAIL_1]") == 2
    assert "[EMAIL_2]" in result.text


def test_restore_puts_the_original_values_back():
    text = "From: Anna Berger <anna@example.com>\nThanks,\nAnna Berger\n+49 30 1234567"
    result = redact(text)
    assert restore(result.text, result.mapping) == text


def test_restore_works_on_new_text_that_uses_placeholders():
    result = redact("Thanks,\nAnna Berger")
    assert restore("Summary for [NAME_1].", result.mapping) == "Summary for Anna Berger."


DEV_CASES = load_golden_cases(split="dev")


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda case: case.case_id)
def test_redaction_removes_all_planted_pii_from_dev_cases(case):
    """Tuned on dev only. Holdout redaction recall is measured by the evaluation in Phase 4."""
    text = ingest((GOLDEN_DIR / "dev" / case.pdf_file).read_bytes()).text
    redacted = flat(redact(text).text)
    for pii in case.pii:
        assert flat(pii.value) not in redacted, pii.kind
    fields = case.expected.fields
    for value in (fields.claim_number, fields.policy_number, fields.location):
        if value is not None:
            assert value in redacted
    if fields.amount_claimed is not None:
        assert f"{fields.amount_claimed:.2f}".removesuffix(".00") in redacted.replace(",", "")
    if fields.police_report_number is not None:
        assert fields.police_report_number in redacted
