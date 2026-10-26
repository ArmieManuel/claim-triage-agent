"""Compare freshly generated golden cases with the committed files, listing every difference.

Usage: python scripts/check_golden.py
Run it inside the Linux container as well as on Windows to prove the generator does not depend
on the operating system or time zone (the CI runner is Linux on UTC):
  docker run --rm -e TZ=UTC -v "<repo>:/app" -w /app claim-triage-agent python scripts/check_golden.py
"""

import json

from generator.make_case import make_case
from generator.scenarios import build_specs
from triage.golden import GOLDEN_DIR, load_golden_cases


def main() -> int:
    committed = {case.case_id: case for case in load_golden_cases()}
    differences = 0
    for spec in build_specs():
        generated = make_case(spec)
        new = json.loads(generated.case.model_dump_json())
        old = json.loads(committed[spec.case_id].model_dump_json())
        if new != old:
            differences += 1
            changed = sorted(k for k in set(new) | set(old) if new.get(k) != old.get(k))
            detail = {k: (old.get(k), new.get(k)) for k in changed if k != "expected"}
            print(f"{spec.case_id}: fields differ {changed} {str(detail)[:300]}")
        pdf = (GOLDEN_DIR / spec.split / generated.case.pdf_file).read_bytes()
        if generated.pdf_bytes != pdf:
            differences += 1
            print(f"{spec.case_id}: PDF bytes differ")
    print(f"{differences} differences in {len(committed)} cases")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
