---
name: build-eval-dataset
description: Create or extend a gold-labelled evaluation dataset for one component (evals/datasets/<component>.jsonl) with dev/test split, balanced classes, hard cases and labelling notes. Use before building or tuning a component, or when an eval reveals uncovered cases.
---

# Build an eval dataset

Gold data is the answer key. A bad answer key makes every metric meaningless, so quality beats quantity.

## Steps
1. **Define the gold label per row** for the component (see `docs/course-notes.md` §8). Typical schemas:
   - router: `{"id", "message", "history", "gold_intent", "split"}`
   - collector: `{"id", "question", "profile", "gold_slots", "gold_needs_clarification", "split"}`
   - retrieval: `{"id", "query", "gold_section_ids": [...], "split"}`
   - answerer: `{"id", "query", "profile", "gold_answer", "gold_section_ids", "gold_sufficient", "split"}`
   - leave agent: `{"id", "employee_id", "turns": [...], "gold_db_state", "gold_tool_sequence", "split"}`
2. **Cover the space deliberately**, not just easy cases:
   - every class or intent, with no class under ~10% of rows;
   - paraphrases, typos, short and long phrasing;
   - **negation and mixed intents** ("I don't want leave, just tell me the rules");
   - cases that need clarification vs cases already answerable from the profile;
   - **out-of-scope and near-miss** questions (topics close to the policies but not covered) for HR referral;
   - adversarial rows (prompt injection, requests for other employees' data).
3. **Gold labels come from the corpus, not from the model.** If an LLM drafts rows, every label is checked by hand against `data/policies/` before it goes in. Mark each row `"origin": "manual" | "llm_drafted_checked"`.
4. **Split.** Use ~40% dev and ~60% test, stratified by label. Never tune prompts on test.
5. **Size guide:** router ≥ 60, collector ≥ 40, retrieval ≥ 50 queries, answerer ≥ 40, leave agent ≥ 25 scenarios, end-to-end ≥ 30.
6. Print label distribution and split counts, and add them to `data/README.md` (data card).
7. Record the step with `crisp-dm-step` (phase 3 Data Preparation).
