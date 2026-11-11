"""Rule engine evaluation = the unit-test suite (every rule in docs/crisp-dm.md §1.4). Saves pass rate."""

from __future__ import annotations

import re
import subprocess
import sys

from evals.common import ROOT, save


def main() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_rules.py", "-q", "-rA", "--no-header"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    lines = out.stdout.splitlines()
    per_row = [
        {"test": m.group(2), "outcome": m.group(1)}
        for line in lines
        if (m := re.match(r"^(PASSED|FAILED|ERROR) tests/test_rules.py::(\S+)", line))
    ]
    passed = sum(r["outcome"] == "PASSED" for r in per_row)
    save(
        "rules",
        {
            "tests": len(per_row),
            "passed": passed,
            "pass_rate": round(passed / len(per_row), 3) if per_row else 0.0,
        },
        per_row,
        "all",
    )


if __name__ == "__main__":
    main()
