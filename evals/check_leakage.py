"""Prompt/eval leakage check: lists every eval item that shares a 6-word sequence with a prompt file.

Few-shot examples that copy eval items make the corresponding scores optimistic. Run before reporting numbers:
python -m evals.check_leakage   (writes evals/results/leakage__all.json)
"""

from __future__ import annotations

import json
import re

from evals.common import DATASETS, ROOT, save

N = 6


def ngrams(text: str) -> set[str]:
    w = re.findall(r"[a-z]+", text.lower())
    return {" ".join(w[i : i + N]) for i in range(len(w) - N + 1)}


def main() -> None:
    prompts = {
        p.stem: ngrams(p.read_text(encoding="utf-8"))
        for p in (ROOT / "src/hr_assistant/prompts").glob("*.md")
    }
    per_row = []
    for f in sorted(DATASETS.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            texts = [r.get("question") or r.get("message") or "", *r.get("turns", [])]
            for t in texts:
                g = ngrams(t)
                for name, pg in prompts.items():
                    shared = g & pg
                    if shared:
                        per_row.append(
                            {
                                "dataset": f.stem,
                                "id": r.get("id"),
                                "split": r.get("split"),
                                "prompt": name,
                                "item": t,
                                "shared": sorted(shared)[:2],
                                "exact_item_in_prompt": len(g) > 0 and g <= pg,
                            }
                        )
    by_split: dict[str, int] = {}
    for p in per_row:
        by_split[f"{p['dataset']}:{p['split']}"] = by_split.get(f"{p['dataset']}:{p['split']}", 0) + 1
    save(
        "leakage",
        {
            "overlapping_items": len(per_row),
            "exact_items_copied_into_prompts": sorted(
                {
                    f"{p['dataset']}:{p['id']} ({p['split']}) -> {p['prompt']}"
                    for p in per_row
                    if p["exact_item_in_prompt"]
                }
            ),
            "by_dataset_split": by_split,
        },
        per_row,
        "all",
    )


if __name__ == "__main__":
    main()
