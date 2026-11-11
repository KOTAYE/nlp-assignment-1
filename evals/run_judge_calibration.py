"""Judge calibration ("a benchmark for the judge", Evaluation lecture): run the correctness judge on controlled
examples whose verdict is known by construction, and report agreement."""

from __future__ import annotations

from collections import Counter

from evals.common import binary_report, load, save
from evals.judge import judge_correctness

PASS = {"fully_matches", "mostly_right"}
LEVELS = ["fully_matches", "mostly_right", "mostly_wrong", "contradicts"]


def main() -> None:
    rows = load("judge_calibration")
    per_row = []
    for r in rows:
        v = judge_correctness(r["question"], r["gold_answer"], r["candidate"])
        per_row.append(
            {
                "id": r["id"],
                "expected": r["expected"],
                "judge": v.verdict,
                "reason": v.reason,
                "exact": v.verdict == r["expected"],
                "adjacent": abs(LEVELS.index(v.verdict) - LEVELS.index(r["expected"])) <= 1,
            }
        )
    exact = sum(p["exact"] for p in per_row) / len(per_row)
    adjacent = sum(p["adjacent"] for p in per_row) / len(per_row)
    binary = binary_report([p["expected"] in PASS for p in per_row], [p["judge"] in PASS for p in per_row])
    contradiction = binary_report(
        [p["expected"] == "contradicts" for p in per_row], [p["judge"] == "contradicts" for p in per_row]
    )
    save(
        "judge_calibration",
        {
            "exact_agreement": round(exact, 3),
            "within_one_level": round(adjacent, 3),
            "pass_fail_accuracy": binary["accuracy"],
            "pass_fail_mcc": binary["mcc"],
            "contradiction_recall": contradiction["recall"],
            "contradiction_precision": contradiction["precision"],
            "confusion": dict(Counter(f"{p['expected']}->{p['judge']}" for p in per_row)),
        },
        per_row,
        "all",
        prompts=("judge_correctness",),
    )


if __name__ == "__main__":
    main()
