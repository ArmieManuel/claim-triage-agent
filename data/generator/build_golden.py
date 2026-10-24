"""Writes the golden dataset to data/golden/{dev,holdout}.

Run: python -m generator.build_golden
"""

import shutil

from generator.make_case import make_case
from generator.scenarios import build_specs
from triage.golden import GOLDEN_DIR


def main() -> None:
    for split in ("dev", "holdout"):
        folder = GOLDEN_DIR / split
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
    for spec in build_specs():
        generated = make_case(spec)
        folder = GOLDEN_DIR / spec.split
        (folder / generated.case.pdf_file).write_bytes(generated.pdf_bytes)
        (folder / f"{spec.case_id}.json").write_text(
            generated.case.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(build_specs())} cases to {GOLDEN_DIR}")


if __name__ == "__main__":
    main()
