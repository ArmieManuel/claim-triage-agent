"""Draw the README charts as SVG from committed evaluation reports (no plotting library).

Usage: .venv\\Scripts\\python scripts\\make_charts.py
Every number comes from reports/<run>/metrics.json or cases.csv (PLAN.md hard rule 2).
Colors: validated categorical slots 1 and 2, with light and dark variants.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = ROOT / "docs" / "images"
RUNS = [  # (label shown, report folder suffix)
    ("Baseline\n(dev)", "_dev_baseline"),
    ("v2 fixes\n(dev)", "_dev_v2-fixes"),
    ("v3\n(dev)", "_dev_v3"),
    ("Holdout\n(unseen)", "_holdout_milestone-phase4"),
]
STYLE = """<style>
  .surface { fill: #fcfcfb; } .ink { fill: #0b0b0b; } .muted { fill: #52514e; }
  .grid { stroke: #e4e3df; } .axis { stroke: #b5b3ad; }
  .s1 { fill: #2a78d6; stroke: #2a78d6; } .s2 { fill: #eb6834; stroke: #eb6834; }
  .ring { stroke: #fcfcfb; } .ref { stroke: #52514e; }
  text { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
  @media (prefers-color-scheme: dark) {
    .surface { fill: #1a1a19; } .ink { fill: #f0efec; } .muted { fill: #c3c2b7; }
    .grid { stroke: #33332f; } .axis { stroke: #5c5b55; }
    .s1 { fill: #3987e5; stroke: #3987e5; } .s2 { fill: #d95926; stroke: #d95926; }
    .ring { stroke: #1a1a19; } .ref { stroke: #c3c2b7; }
  }
</style>"""


def report(suffix: str) -> Path:
    (folder,) = [f for f in REPORTS.iterdir() if f.name.endswith(suffix)]
    return folder


def svg(width: int, height: int, title: str, desc: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img"><title>{title}</title><desc>{desc}</desc>'
        f'{STYLE}<rect class="surface" width="{width}" height="{height}" rx="8"/>{body}</svg>\n'
    )


def accuracy_chart() -> str:
    """Dot plot: routing and field accuracy per run. Dots, not bars, so a zoomed axis is honest."""
    rows = []
    for label, suffix in RUNS:
        m = json.loads((report(suffix) / "metrics.json").read_text(encoding="utf-8"))["metrics"]
        rows.append((label, m["routing_accuracy"], m["field_accuracy_mean"]))
    w, h, left, right, top, bottom = 720, 360, 70, 150, 80, 70
    lo, hi = 0.95, 1.0
    y = lambda v: top + (hi - v) / (hi - lo) * (h - top - bottom)  # noqa: E731
    step = (w - left - right) / len(rows)
    x = lambda i: left + step * (i + 0.5)  # noqa: E731
    parts = [
        f'<text class="ink" x="{left}" y="28" font-size="16" font-weight="600">'
        "Accuracy per evaluation run</text>",
        f'<text class="muted" x="{left}" y="46" font-size="12">'
        "Axis starts at 95%. Dev runs tune prompts; holdout was run once, never tuned on.</text>",
    ]
    for tick in (0.95, 0.96, 0.97, 0.98, 0.99, 1.0):
        parts.append(
            f'<line class="grid" x1="{left}" x2="{w - right}" y1="{y(tick):.1f}" '
            f'y2="{y(tick):.1f}" stroke-width="1"/>'
            f'<text class="muted" x="{left - 8}" y="{y(tick) + 4:.1f}" font-size="11" '
            f'text-anchor="end">{tick:.0%}</text>'
        )
    for i, (label, routing, fields) in enumerate(rows):
        for n, line in enumerate(label.split("\n")):
            cls = "ink" if n == 0 else "muted"
            parts.append(
                f'<text class="{cls}" x="{x(i):.1f}" y="{h - bottom + 22 + 15 * n}" '
                f'font-size="12" text-anchor="middle">{line}</text>'
            )
        parts.append(  # routing: circle
            f'<circle class="s1 ring" cx="{x(i) - 9:.1f}" cy="{y(routing):.1f}" r="6" '
            f'stroke-width="2"><title>{label.split(chr(10))[0]}: routing {routing:.1%}</title></circle>'
        )
        fx, fy = x(i) + 9, y(fields)
        parts.append(  # fields: diamond, a second shape so identity is not color alone
            f'<path class="s2 ring" d="M{fx:.1f} {fy - 7:.1f} L{fx + 7:.1f} {fy:.1f} '
            f'L{fx:.1f} {fy + 7:.1f} L{fx - 7:.1f} {fy:.1f} Z" stroke-width="2">'
            f"<title>{label.split(chr(10))[0]}: fields {fields:.1%}</title></path>"
        )
    last = len(rows) - 1
    parts.append(
        f'<text class="ink" x="{x(last) + 24:.1f}" y="{y(rows[last][1]) - 8:.1f}" font-size="12">'
        f"Routing {rows[last][1]:.0%}</text>"
        f'<text class="ink" x="{x(last) + 24:.1f}" y="{y(rows[last][2]) + 14:.1f}" font-size="12">'
        f"Fields {rows[last][2]:.1%}</text>"
    )
    lx, ly = w - right + 20, top + 10
    parts.append(
        f'<circle class="s1" cx="{lx}" cy="{ly}" r="6"/>'
        f'<text class="ink" x="{lx + 12}" y="{ly + 4}" font-size="12">Routing accuracy</text>'
        f'<path class="s2" d="M{lx} {ly + 17} L{lx + 7} {ly + 24} L{lx} {ly + 31} L{lx - 7} {ly + 24} Z"/>'
        f'<text class="ink" x="{lx + 12}" y="{ly + 28}" font-size="12">Field accuracy</text>'
    )
    return svg(
        w,
        h,
        "Accuracy per evaluation run",
        "Routing and mean field accuracy for the baseline, v2 and v3 dev runs and the holdout run.",
        "".join(parts),
    )


def latency_chart() -> str:
    """Horizontal bars from zero: seconds per holdout claim, with p50 and p95 reference lines."""
    folder = report(RUNS[-1][1])
    with (folder / "cases.csv").open(encoding="utf-8") as f:
        cases = [(r["case_id"], float(r["latency_s"]), r["tags"]) for r in csv.DictReader(f)]
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    cases.sort(key=lambda c: c[1], reverse=True)
    w, left, right, top, row = 720, 90, 190, 64, 18
    h = top + row * len(cases) + 64
    top_value = max(c[1] for c in cases)
    scale = (w - left - right) / top_value
    parts = [
        f'<text class="ink" x="{left}" y="28" font-size="16" font-weight="600">'
        "Seconds per claim, holdout run (20 unseen claims)</text>",
        f'<text class="muted" x="{left}" y="46" font-size="12">'
        "gemma4:e2b on a laptop CPU. Long documents are the slow ones.</text>",
    ]
    for i, (case_id, seconds, tags) in enumerate(cases):
        ytop = top + i * row
        width = max(seconds * scale, 4)
        parts.append(
            f'<text class="muted" x="{left - 8}" y="{ytop + 12}" font-size="11" '
            f'text-anchor="end">{case_id}</text>'
            f'<path class="s1" d="M{left} {ytop + 2} h{width - 4:.1f} a4 4 0 0 1 4 4 v6 '
            f'a4 4 0 0 1 -4 4 h-{width - 4:.1f} Z"><title>{case_id}: {seconds:.1f} s</title></path>'
        )
        if "long_description" in tags:
            parts.append(
                f'<text class="ink" x="{left + width + 6:.1f}" y="{ytop + 12}" font-size="11">'
                f"{seconds:.0f} s, 3,300-word letter</text>"
            )
    bottom_y = top + row * len(cases)
    for n, (name, key) in enumerate((("p50", "latency_p50_s"), ("p95", "latency_p95_s"))):
        rx = left + metrics[key] * scale
        label_y = bottom_y + 16 + 16 * n  # stagger, the two lines are close together
        parts.append(
            f'<line class="ref" x1="{rx:.1f}" x2="{rx:.1f}" y1="{top - 4}" y2="{label_y - 11}" '
            f'stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text class="ink" x="{rx + 4:.1f}" y="{label_y}" font-size="11">'
            f"{name} {metrics[key]:.0f} s</text>"
        )
    parts.append(f'<line class="axis" x1="{left}" x2="{left}" y1="{top - 4}" y2="{bottom_y}"/>')
    return svg(
        w,
        h,
        "Seconds per claim on the holdout run",
        "Horizontal bars of latency per holdout case with p50 and p95 lines.",
        "".join(parts),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in (
        ("accuracy_by_run.svg", accuracy_chart()),
        ("holdout_latency.svg", latency_chart()),
    ):
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"Wrote {OUT / name}")


if __name__ == "__main__":
    main()
