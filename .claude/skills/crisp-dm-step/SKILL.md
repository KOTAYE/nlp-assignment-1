---
name: crisp-dm-step
description: Start or finish any unit of project work inside the CRISP-DM process. Use at the start of every task (name the phase, plan) and at the end (update the phase log and iteration log in docs/crisp-dm.md).
---

# CRISP-DM step

Every task in this repo belongs to one CRISP-DM phase. This skill keeps `docs/crisp-dm.md` the single source of truth for what was decided and why.

## At the start of a task
1. **Name the phase** (1 Business Understanding, 2 Data Understanding, 3 Data Preparation, 4 Modeling, 5 Evaluation, 6 Deployment) and say it to the user in one line.
2. Read only the relevant section of `docs/crisp-dm.md` and, if it is a component task, its row in `docs/architecture.md`.
3. **Check the entry conditions:**
   - Modeling a component requires its eval dataset to exist, or to be created first with `build-eval-dataset`.
   - Evaluation requires the component to run end to end on the dev split.
   - Scope or rule changes require the user's confirmation. Mark them `[proposed]` until confirmed.
4. Write a short plan: files to touch, expected metric impact, and how you will verify it. For non-trivial work, wait for approval.

## At the end of a task
1. Update the phase section in `docs/crisp-dm.md` with the decisions made and the reasons (one or two bullets each, no essays).
2. Append a row to the **Iteration log**: `| # | date | phase | change | metric before → after |`.
   - Metrics must come from a real `evals/results/*.json` file. Write `—` if nothing was measured.
3. If the iteration was triggered by an eval failure, name the **first failing stage** (parse → chunk → retrieve → rank → assemble → generate, or route → collect → tool) and the fix.
4. Keep `docs/architecture.md` in sync if a component's input, output or model calls changed.
5. Commit with a message that names the phase, e.g. `Modeling: add hybrid retriever with RRF`.
