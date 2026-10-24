"""Rule-based PII redaction, run before any model call.

Two kinds of detectors:
- patterns: emails, IBANs, phone numbers, national IDs, postcode-anchored addresses
- context cues: labels ("Claimant name"), "From:", sign-offs ("Thanks,"), "my client, X,"

Every value found is replaced everywhere it occurs, also when a line break splits it.
The placeholder mapping stays inside the service so results can be restored for the handler.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")
CODICE_FISCALE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")
PHONE = re.compile(
    r"(?<![\w/.-])(?:0\d{2,4}/\d{5,10}"  # Austrian style 0316/20198674 (not dates: 03/03/2026)
    r"|(?:\+\d{2} ?(?:\(0\) ?)?|\(0|0)\d[\d ()-]{5,}\d)"
)
TAX_ID_DE = re.compile(r"(?<![\w/.-])[1-9]\d{10}(?!\w)")
SOCIAL_ID_AT = re.compile(r"(?<![\w/.-])\d{10}(?!\w)")
PLATE_SENTENCE = re.compile(r"registration is\s+([A-Z0-9][A-Z0-9 -]{1,12}?[A-Z0-9])\.(?:\s|$)")
PLATE_LABEL = re.compile(r"^(?:Vehicle registration|Reg\. number|Vehicle reg)[ \t]+(.+)$", re.M)
POSTCODE_TOWN = re.compile(r"(?<![\w/.,-])\d{4,5},?[ \t]+[A-ZÄÖÜ]")
ADDRESS_LABEL = re.compile(r"^(?:Home address|Correspondence address|Address)[ \t]+")
NAME_CUES = (
    re.compile(r"^(?:Claimant name|Full name|Name|Policyholder name)[ \t]+([^\n]+)$", re.M),
    re.compile(r"^From:[ \t]*([^<\n]+?)[ \t]*<", re.M),
    re.compile(
        r"^(?:Thanks|Yours faithfully|Yours sincerely|Kind regards|Best regards|Regards),?"
        r"[ \t]*\n([^\n]+)$",
        re.M,
    ),
    re.compile(r"my client,\s+([^,]+?),\s+who"),
    re.compile(r"your policyholder,\s+([^\n]+?(?:\n[^\n]+?)?)\.[ \t]*\n"),
)


@dataclass
class Redaction:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original value


def flexible(value: str) -> str:
    """Regex matching the value with any whitespace (spaces or line breaks) between its words."""
    return r"\s+".join(re.escape(token) for token in value.split())


class _Redactor:
    def __init__(self, text: str):
        self.text = text
        self.mapping: dict[str, str] = {}
        self._placeholders: dict[tuple[str, str], str] = {}
        self._counts: Counter[str] = Counter()

    def replace(self, kind: str, value: str) -> None:
        value = value.strip()
        if not value or value.startswith("["):
            return
        key = (kind, " ".join(value.split()))
        if key not in self._placeholders:
            self._counts[kind] += 1
            placeholder = f"[{kind}_{self._counts[kind]}]"
            self._placeholders[key] = placeholder
            self.mapping[placeholder] = value
        self.text = re.sub(flexible(value), self._placeholders[key], self.text)

    def replace_matches(self, kind: str, pattern: re.Pattern[str], group: int = 0) -> None:
        for value in dict.fromkeys(m.group(group) for m in pattern.finditer(self.text)):
            self.replace(kind, value)


def _phones(text: str) -> list[str]:
    found = []
    for match in PHONE.finditer(text):
        value = match.group(0).strip()
        if sum(ch.isdigit() for ch in value) >= 8:
            found.append(value)
    return found


def _addresses(text: str) -> list[str]:
    lines = text.split("\n")
    found = []
    for i, line in enumerate(lines):
        match = POSTCODE_TOWN.search(line)
        if not match:
            continue
        prefix = ADDRESS_LABEL.sub("", line[: match.start()]).strip()
        town = line[match.start() :].strip()
        if prefix:
            street, joiner = prefix.rstrip(","), ", "
        elif i > 0:
            street, joiner = ADDRESS_LABEL.sub("", lines[i - 1]).strip(), "\n"
        else:
            continue
        if any(ch.isdigit() for ch in street) and not street.startswith("["):
            found.append(f"{street}{joiner}{town}" if prefix else f"{street}\n{town}")
    return found


def _names(text: str) -> list[str]:
    names = []
    for cue in NAME_CUES:
        for match in cue.finditer(text):
            name = " ".join(match.group(1).split())
            if (
                name
                and not name.startswith("[")
                and len(name) <= 60
                and not any(ch.isdigit() for ch in name)
            ):
                names.append(name)
    # Longest first, so "Dr. Anna Berger" is replaced before "Anna Berger".
    return sorted(dict.fromkeys(names), key=len, reverse=True)


def redact(text: str) -> Redaction:
    r = _Redactor(text)
    r.replace_matches("EMAIL", EMAIL)
    r.replace_matches("IBAN", IBAN)
    r.replace_matches("ID", CODICE_FISCALE)
    for phone in _phones(r.text):
        r.replace("PHONE", phone)
    r.replace_matches("ID", TAX_ID_DE)
    r.replace_matches("ID", SOCIAL_ID_AT)
    r.replace_matches("PLATE", PLATE_SENTENCE, group=1)
    r.replace_matches("PLATE", PLATE_LABEL, group=1)
    for address in _addresses(r.text):
        r.replace("ADDRESS", address)
    for name in _names(r.text):
        r.replace("NAME", name)
    return Redaction(text=r.text, mapping=r.mapping)


def restore(text: str, mapping: dict[str, str]) -> str:
    for placeholder, value in mapping.items():
        text = text.replace(placeholder, value)
    return text
