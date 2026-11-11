"""Retrieval evaluation (brief: "retrieval success"). Deterministic metrics against gold section IDs:
Hit@k, Recall@k, MRR@10, nDCG@5 for BM25, dense, hybrid (RRF) and hybrid + cross-encoder reranker."""

from __future__ import annotations

from evals.common import load, mean_dicts, ranking_metrics, save, split_arg
from hr_assistant.retrieval import get_stack


def main() -> None:
    args = split_arg("dev")
    rows = [r for r in load("qa", args.split) if r["gold_outcome"] == "answer"]
    stack = get_stack()
    variants = {
        "bm25": lambda q: stack.bm25.search(q, k=10),
        "dense": lambda q: stack.dense.search(q, k=10),
        "hybrid_rrf": lambda q: stack.hybrid.search(q, k=10),
        "hybrid_rrf+rerank": lambda q: stack.reranker.rerank(q, stack.hybrid.search(q, k=20), k=10),
    }
    summary = {}
    per_row = []
    for name, fn in variants.items():
        scores = []
        for r in rows:
            ranked = [c.id for c, _ in fn(r["question"])]
            m = ranking_metrics(ranked, set(r["gold_section_ids"]))
            scores.append(m)
            per_row.append(
                {
                    "variant": name,
                    "id": r["id"],
                    "question": r["question"],
                    "gold": r["gold_section_ids"],
                    "top5": ranked[:5],
                    **m,
                }
            )
        summary[name] = mean_dicts(scores)
    misses = [
        f"{p['id']} {p['question']!r} gold={p['gold']} top5={p['top5']}"
        for p in per_row
        if p["variant"] == "hybrid_rrf+rerank" and p["hit@5"] == 0
    ]
    save(
        "retrieval",
        {"by_variant": summary, "production_variant": "hybrid_rrf+rerank", "misses_at_5": misses},
        per_row,
        args.split,
    )
    for name, m in summary.items():
        print(f"  {name:20s} " + "  ".join(f"{k}={v:.3f}" for k, v in m.items()))


if __name__ == "__main__":
    main()
