"""Renders claim facts into one of three PDF layouts with ReportLab platypus."""

import io
import random
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from generator.content import LABELS

FOOTER = "SYNTHETIC TEST DOCUMENT - generated for software testing, not a real claim."
STYLES = getSampleStyleSheet()


@dataclass
class Facts:
    """Display strings for one document. None means the document does not state it."""

    insurer: str
    claim_number: str
    policy_number: str | None
    date_of_loss: str | None
    role: str
    role_text: str
    amount: str | None
    location: str
    policy_start: str
    police_report: str | None
    writer_name: str
    other_name: str | None
    address: str
    address_lines: list[str]
    phone: str
    email: str
    national_id: str
    national_id_labels: tuple[str, ...]
    national_id_name: str
    vehicle_registration: str | None
    description: str
    sent_date: str
    extra_paragraphs: list[str] = field(default_factory=list)


def para(text: str, style: str = "BodyText") -> Paragraph:
    return Paragraph(escape(text), STYLES[style])


def paragraphs(text: str, words_per_paragraph: int = 150) -> list[Paragraph]:
    words = text.split()
    chunks = [words[i : i + words_per_paragraph] for i in range(0, len(words), words_per_paragraph)]
    return [para(" ".join(chunk)) for chunk in chunks]


def label(key: str, rng: random.Random) -> str:
    return rng.choice(LABELS[key])


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawString(20 * mm, 10 * mm, f"{FOOTER} Page {doc.page}")
    canvas.restoreState()


def two_column_table(rows: list[tuple[str, str]]) -> Table:
    data = [[para(k), para(v)] for k, v in rows]
    table = Table(data, colWidths=[55 * mm, 115 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def form_story(f: Facts, rng: random.Random) -> list:
    claim_rows = [
        (label("claim_number", rng), f.claim_number),
        (label("policy_number", rng), f.policy_number),
        (label("date_of_loss", rng), f.date_of_loss),
        (label("claimant_role", rng), f.role_text),
        (label("amount_claimed", rng), f.amount),
        (label("location", rng), f.location),
        (label("policy_start_date", rng), f.policy_start),
        (label("police_report_number", rng), f.police_report),
    ]
    claim_rows = [(k, v) for k, v in claim_rows if v is not None]
    rng.shuffle(claim_rows)
    person_rows = [
        (label("name", rng), f.writer_name),
        (label("address", rng), f.address),
        (label("phone", rng), f.phone),
        (label("email", rng), f.email),
        (rng.choice(f.national_id_labels), f.national_id),
    ]
    if f.vehicle_registration:
        person_rows.append((label("vehicle_registration", rng), f.vehicle_registration))
    if f.other_name:
        person_rows.append(("Policyholder name", f.other_name))
    sections = [
        ("Claim details", two_column_table(claim_rows)),
        ("Claimant details", two_column_table(person_rows)),
    ]
    rng.shuffle(sections)
    story = [para(f"{f.insurer}: Claim Notification Form", "Title")]
    for heading, table in sections:
        story += [para(heading, "Heading2"), table, Spacer(1, 4 * mm)]
    story.append(para(rng.choice(("Description of loss", "What happened", "Details")), "Heading2"))
    story += paragraphs(f.description)
    story += [para(text) for text in f.extra_paragraphs]
    story += [Spacer(1, 4 * mm), para(f"Form completed on {f.sent_date}.")]
    return story


def opening(f: Facts) -> str:
    if f.role == "representative":
        return f"I am writing on behalf of my client, {f.other_name}, who holds the policy."
    if f.role == "third_party":
        return f"I am writing to make a claim against your policyholder, {f.other_name}."
    return "I am writing to make a claim under my policy."


def fact_sentences(f: Facts) -> list[str]:
    when = f" on {f.date_of_loss}" if f.date_of_loss else ""
    sentences = [f"The incident happened{when} in {f.location}."]
    if f.amount:
        sentences.append(f"The amount claimed is {f.amount}.")
    sentences.append(f"The policy has been in force since {f.policy_start}.")
    if f.police_report:
        sentences.append(f"The police reference is {f.police_report}.")
    if f.vehicle_registration:
        sentences.append(f"The vehicle registration is {f.vehicle_registration}.")
    sentences.append(f"For identification, the {f.national_id_name} is {f.national_id}.")
    return sentences


def letter_story(f: Facts, rng: random.Random) -> list:
    story = [para(line) for line in [f.writer_name, *f.address_lines, f.phone, f.email]]
    story += [Spacer(1, 6 * mm), para(f.sent_date), Spacer(1, 4 * mm)]
    story += [para("Claims Department"), para(f.insurer), Spacer(1, 6 * mm)]
    subject = f"Re: claim {f.claim_number}"
    if f.policy_number:
        subject += f", policy {f.policy_number}"
    story += [para(subject, "Heading3"), para("Dear Sir or Madam,"), para(opening(f))]
    facts = fact_sentences(f)
    rng.shuffle(facts)
    story += paragraphs(f.description)
    story.append(para(" ".join(facts)))
    story += [para(text) for text in f.extra_paragraphs]
    story += [para("Please contact me if you need anything further."), Spacer(1, 4 * mm)]
    story += [para("Yours faithfully,"), para(f.writer_name)]
    return story


def email_story(f: Facts, rng: random.Random) -> list:
    domain = f.insurer.lower().replace(" ", "") + ".example"
    subject = rng.choice((f"Claim {f.claim_number}", f"New claim, ref {f.claim_number}"))
    headers = [
        f"From: {f.writer_name} <{f.email}>",
        f"To: claims@{domain}",
        f"Sent: {f.sent_date}",
        f"Subject: {subject}",
    ]
    story = [para(line) for line in headers] + [Spacer(1, 6 * mm), para("Hello,")]
    story.append(para(opening(f)))
    if f.policy_number:
        story.append(para(f"My policy number is {f.policy_number}."))
    story += paragraphs(f.description)
    story.append(para(" ".join(fact_sentences(f))))
    story += [para(text) for text in f.extra_paragraphs]
    story += [para("Thanks,"), para(f.writer_name), para(f.phone), para(f.address)]
    return story


LAYOUTS = {"form": form_story, "letter": letter_story, "email": email_story}


def render_pdf(layout: str, facts: Facts, rng: random.Random, title: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="claim-triage-agent synthetic generator",
        invariant=1,
    )
    doc.build(LAYOUTS[layout](facts, rng), onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
