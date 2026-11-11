---
name: add-component
description: Implement or change a pipeline component (guard, router, collector, rewriter, retriever, reranker, answerer, leave_agent, referral) following the project conventions — module, prompt file, Pydantic schema, tracing, unit tests, and its eval. Use whenever adding or modifying a component in src/hr_assistant/components/.
---

# Add or change a component

A component is **done** only when all the boxes below are ticked. Show this checklist to the user at the end, with each item ticked or explained.

## Checklist
- [ ] **Contract first.** Write the input → output types in `src/hr_assistant/schemas.py` (Pydantic). LLM outputs that code consumes are always a schema, never free text.
- [ ] **Module** `src/hr_assistant/components/<name>.py` exposes one public function, e.g. `route(message: str, history: list[Turn]) -> RouteResult`. It has no UI or DB imports. DB access goes only through `tools/`.
- [ ] **Prompt** in `src/hr_assistant/prompts/<name>.md`, if the component uses an LLM. It contains: role and scope, rules, the output contract (the JSON schema), and 2–4 few-shot examples with shuffled labels. The prompt version is a header line `version: N`, bumped on every change.
- [ ] **LLM calls only via** `llm.py` (`complete_json(component=..., prompt=..., schema=...)`). This guarantees tracing (component, prompt version, tokens, latency) and uses temperature 0 for classification, extraction and tool calls.
- [ ] **Deterministic parts stay in code.** Dates, working-day arithmetic, balances and rule decisions are never computed by the LLM.
- [ ] **Unit tests** in `tests/test_<name>.py` for the deterministic logic and the schema validation. Mock the LLM, so no network is needed.
- [ ] **Eval exists.** `evals/datasets/<name>.jsonl` (use `build-eval-dataset`) and `evals/run_<name>.py` (use `run-evals`). Run it on **dev**.
- [ ] **Baseline comparison** where it makes sense: router LLM vs TF-IDF+LogReg, retriever BM25 vs dense vs hybrid, with vs without the reranker or the rewriter.
- [ ] **Docs.** Update the component row in `docs/architecture.md` and record the step with `crisp-dm-step`.

## Tool-specific rules (leave agent, referral)
- A tool is a typed contract: a description that says *when* to use it, enums for closed sets (`leave_type`, `decision`), defaults, and small return objects.
- Errors are instructive: `{"error": ..., "message": ..., "hint": ..., "retryable": bool}`.
- The current employee's ID is injected by the harness, never taken from model arguments (access control).
- `decide_leave` is available only to the HR role and needs explicit confirmation in the conversation.
- The agent loop has `max_steps` and repeated-call detection. Log the stop reason.
