---
name: run-evals
description: Write or run a component evaluation (evals/run_<component>.py), save metrics to evals/results/, and interpret them — error analysis, first failing stage, next improvement. Use when evaluating a component, comparing variants, or before reporting any number.
---

# Run evals

## Writing an eval script (`evals/run_<component>.py`)
- CLI: `python -m evals.run_<component> --split dev|test [--variant NAME]`.
- Call the component through its public function, exactly as the pipeline does.
- **Assertions beat judges.** Compute deterministic metrics in code:
  - classification: confusion matrix, per-class P/R/F1, macro-F1, MCC (`sklearn.metrics`);
  - retrieval: Hit@k, Recall@k, MRR, nDCG@k against `gold_section_ids`;
  - agent: final DB-state equality, tool-sequence match, stop reason, steps, tokens; **pass^k** = all k repeated runs succeed.
- LLM-as-judge (correctness, Faithfulness, Answer Relevancy) only with:
  - a rubric in `src/hr_assistant/prompts/judge_<metric>.md`;
  - temperature 0 and a JSON verdict with a reason;
  - a **calibration** run on ~15 hand-labelled rows, reporting judge–human agreement.
- Save `evals/results/<component>[__<variant>].json`: `{metrics, per_row_errors, split, variant, model, prompt_versions, date, git_commit, n}`.

## Interpreting results (always, in `docs/crisp-dm.md` §5)
1. **Table:** metric, value, target from §1.6, and pass/fail.
2. **What a high or low score means** for this metric, in one line.
3. **Error analysis:** group the failed rows (from `per_row_errors`) into 2–4 failure types with one example each.
4. **First failing stage:** for retrieval and answers, check whether the gold section was retrieved before blaming generation.
5. **Next improvement:** one concrete change. Re-run on **dev**, log before → after with `crisp-dm-step`.
6. Report **final** numbers on **test** only after tuning is finished.

Never write a number into docs that is not in a results file.
