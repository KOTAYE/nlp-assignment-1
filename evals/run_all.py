"""Run every component evaluation on one split. Usage: python -m evals.run_all --split test

Order follows the data flow (docs/architecture.md). Deterministic evals run first; LLM evals cost a few cents.
"""

from __future__ import annotations

import subprocess
import sys

from evals.common import ROOT


def main() -> None:
    split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "test"
    jobs = [
        ["evals.run_rules"],
        ["evals.run_guard", "--split", split],
        ["evals.run_indexer", "--split", "all"],
        ["evals.run_router", "--split", split],
        ["evals.run_collector", "--split", split],
        ["evals.run_rewriter", "--split", split],
        ["evals.run_retrieval", "--split", split],
        ["evals.run_judge_calibration"],
        ["evals.run_qa", "--split", split, "--variant", "pipeline"],
        ["evals.run_qa", "--split", split, "--variant", "oracle"],
        ["evals.run_leave_agent", "--split", split, "--k", "3" if split == "test" else "1"],
        ["evals.run_e2e", "--split", split],
    ]
    for job in jobs:
        print(f"\n######## {' '.join(job)}", flush=True)
        subprocess.run([sys.executable, "-m", *job], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()
