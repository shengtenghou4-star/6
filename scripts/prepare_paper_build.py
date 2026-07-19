from __future__ import annotations

import argparse
from pathlib import Path


START = "## 6. Summary table"
END = "## 7. Prospective test"

REPLACEMENT = """## 6. Summary of completed evidence

- **Alignment placebo:** the correctly aligned residual beats 4,000 of 4,000 baseline-preserving placebos; empirical upper-tail `p=0.00025`.
- **Threshold-free dose response:** one-standard-deviation residual-uplift slope `+0.004430`; event-cluster 95% interval `[+0.003316,+0.005515]`.
- **Distribution:** positive slopes for 8/8 bookmakers, 3/3 selected outcomes and 4/4 cutoffs; leave-one-book-out lower bounds remain above zero.
- **Matched historical return:** residual ROI `+0.565%` versus raw ROI `-0.747%`; paired uncertainty crosses zero.
- **Execution stress:** incremental point return is positive in 60/64 cells, but no practical envelope validates execution.
- **Outcome concentration:** realized uplift is home-dependent at the point-estimate level, while residual standalone closing value is positive in all 12 outcome-by-mechanism cells.
- **Future transfer:** the frozen prospective campaign remains in progress.

"""


def prepare(text: str) -> str:
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("summary-table section markers were not found in order")
    return text[:start] + REPLACEMENT + text[end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="paper/manuscript.md")
    parser.add_argument("--output", default="artifacts/paper/manuscript-build.md")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prepare(source.read_text(encoding="utf-8")), encoding="utf-8")
    print({"input": str(source), "output": str(output), "status": "prepared"})


if __name__ == "__main__":
    main()
