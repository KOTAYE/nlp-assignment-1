"""Query rewriter evaluation on follow-up questions.

Direct: key-term coverage (every gold term group must appear in the rewritten query) and standalone length check.
Ablation: Hit@5 / Recall@5 / MRR of the production retriever with (a) the raw follow-up, (b) the follow-up
concatenated with the previous user turn (cheap baseline), (c) the LLM rewrite.
"""

from __future__ import annotations

from evals.common import load, mean_dicts, ranking_metrics, save, split_arg
from hr_assistant.components.rewriter import rewrite
from hr_assistant.retrieval import get_stack


def main() -> None:
    args = split_arg("dev")
    rows = load("rewriter", args.split)
    stack = get_stack()
    per_row = []
    by_variant: dict[str, list[dict]] = {"raw_followup": [], "concat_previous_turn": [], "llm_rewrite": []}
    coverage = []
    for r in rows:
        q = rewrite(r["question"], r["history"], {})
        groups_ok = [any(t.lower() in q.lower() for t in g) for g in r["gold_term_groups"]]
        coverage.append(all(groups_ok))
        queries = {
            "raw_followup": r["question"],
            "concat_previous_turn": r["history"][0]["content"] + " " + r["question"],
            "llm_rewrite": q,
        }
        row = {
            "id": r["id"],
            "followup": r["question"],
            "rewrite": q,
            "term_groups_ok": groups_ok,
            "gold": r["gold_section_ids"],
        }
        for name, query in queries.items():
            ranked = [c.id for c, _ in stack.retrieve(query, k_final=10)]
            m = ranking_metrics(ranked, set(r["gold_section_ids"]))
            by_variant[name].append(m)
            row[name] = {"hit@5": m["hit@5"], "mrr@10": m["mrr@10"], "top3": ranked[:3]}
        per_row.append(row)
    metrics = {
        "key_term_coverage": round(sum(coverage) / len(coverage), 3),
        "avg_query_words": round(sum(len(p["rewrite"].split()) for p in per_row) / len(per_row), 1),
        "retrieval_ablation": {k: mean_dicts(v) for k, v in by_variant.items()},
    }
    save("rewriter", metrics, per_row, args.split, prompts=("rewriter",))
    for k, v in metrics["retrieval_ablation"].items():
        print(f"  {k:22s} hit@5={v['hit@5']:.3f} recall@5={v['recall@5']:.3f} mrr@10={v['mrr@10']:.3f}")


if __name__ == "__main__":
    main()
