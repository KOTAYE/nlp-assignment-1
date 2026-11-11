# CLAUDE.md — HR Assistant (NLP Assignment 1)

Instructions for the AI coding agent working in this repository. Read this file fully before any task.

## 1. Project in one paragraph

An **HR assistant** for employees. It answers questions about HR procedures (leave, onboarding, benefits, internal requests) using a small corpus of fictional company policies, and **cites the policy section** it used. If needed information is missing (for example the employee's type of leave or dates), it **asks follow-up questions first**. It handles **leave requests**: it creates, tracks and approves/declines them in a database that is reached **only through LLM tool calls**. When the policies do not support an answer, it **routes the question to HR** and does not guess.
This is a graded assignment, and vanilla RAG is explicitly not accepted. Every component must be evaluated.

## 2. How to work: CRISP-DM is mandatory

Every piece of work belongs to one CRISP-DM phase. Before starting a task, name the phase. When finishing, update the phase log in `docs/crisp-dm.md`.

| Phase | What it means here | Output artifact |
|---|---|---|
| 1. Business Understanding | Scope, user stories, success criteria, metric targets | `docs/crisp-dm.md` §1 |
| 2. Data Understanding | Survey existing datasets **before** generating synthetic data; describe the corpus | `docs/crisp-dm.md` §2, `data/README.md` |
| 3. Data Preparation | Policies corpus, chunking, eval datasets with gold labels | `data/`, scripts in `src/data/` |
| 4. Modeling | Build components (prompts, retrieval, agent, tools) | `src/` |
| 5. Evaluation | Per-component metrics, error analysis, improvement ideas | `evals/`, `docs/crisp-dm.md` §5 |
| 6. Deployment | Runnable UI, setup instructions, demo script | `app/`, `README.md` |

The cycle is iterative. If an evaluation shows a weakness, go back to the relevant phase and **log the iteration** (what changed, metric before → after).

## 3. Rules for the agent

- **Use the project skills** (`.claude/skills/`): `crisp-dm-step` at the start and end of every task, `add-component` for any component work, `build-eval-dataset` before building or tuning a component, and `run-evals` before reporting any number.
- **Plan before coding.** For any non-trivial change, state the plan (files, components, eval impact) and wait for approval.
- **Do not decide scope alone.** Business logic, metric targets and model choice are the user's decisions. Propose options with a recommendation.
- **Every component ships with its eval.** A component counts as done only when it has: an eval dataset with gold labels, an eval script, and a recorded metric in `evals/results/`.
- **Small steps.** One component or one concern per change. Do not refactor unrelated code.
- **Do not invent results.** Never write metric numbers into docs unless they came from an actual eval run. Report failures honestly.
- **Explainability.** The user must be able to explain each component in a demo video. Prefer simple, readable designs over clever ones.
- **Context hygiene.** Do not load whole lecture files or large datasets into context. Use `docs/course-notes.md` (condensed lecture notes) and sample a few rows of data. Open a specific lecture in `course/` only for a specific question.
- **Lowest sufficient autonomy.** If the code can decide a step (a workflow), do not hand it to an agent loop. Use the LLM agent only where steps depend on observations (the leave-request flow, agentic retrieval).
- **Tools are typed contracts.** Use JSON-schema tools with enums and defaults, instructive errors (`retryable`, `hint`) and native function calling. Never regex-parse model output. Irreversible actions (approve/decline leave) go behind a confirmation gate.

## 4. Code conventions

- Python 3.12, type hints everywhere, small pure functions where possible.
- Formatting/linting: `ruff format` + `ruff check`. Tests: `pytest`.
- Configuration comes **only** from `.env` via one settings module: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. Never hard-code keys, URLs or model names.
- **All LLM calls go through one client wrapper** (OpenAI-compatible API, OpenRouter by default). The wrapper logs every call (component name, prompt, response, latency, tokens) for tracing and the demo.
- Prompts live in separate files (`src/prompts/`), not inline strings, so they can be versioned and discussed.
- LLM outputs that code consumes must be **structured** (JSON schema / Pydantic) and validated.
- The leave-request DB (SQLite) is touched **only** by tool functions that the LLM agent calls. The UI never queries it directly.
- Use English for code, comments, commit messages and docs. Talk to the user in Ukrainian.

## 5. Evaluation conventions

- Eval data: `evals/datasets/<component>.jsonl`, hand-checked gold labels.
- Eval scripts: `evals/run_<component>.py`. Results go to `evals/results/<component>.json` together with model name, date and git commit.
- Required metric areas (from the brief): **information collection, retrieval success, answer correctness, source support (groundedness/citations), correct referral to HR**, plus the leave-request flow.
- Use the course's terminology and the metric map in `docs/course-notes.md` §8. Report both **intrinsic** (per component) and **extrinsic** (end-to-end scenarios) results.
- **"Assertions beat judges"**: whatever can be checked in code must be checked in code (confusion matrix / F1 / MCC, Hit@k / Recall@k / MRR, DB-state assertions, tool-call sequence). LLM-as-judge (Faithfulness, Answer Relevancy) only where meaning matters, with a written rubric and a small human-labelled calibration sample ("a benchmark for the judge").
- Measure retrieval and generation **separately**. When quality is low, find the **first stage that loses evidence** (parse → chunk → retrieve → rank → assemble → generate) before touching prompts.
- Keep a **dev/test split**: tune prompts and parameters on dev, report final numbers on test. Change one factor at a time and log the prompt version.
- Agents: evaluate the **trajectory, not just the answer** (outcome, process, efficiency, safety, communication). Use at least 20–50 end-to-end tasks, success rate split by stop reason, and pass^k for consistency.
- Each result needs an interpretation: what counts as a good or bad score, why the score is what it is, and the next improvement.

## 6. Git

- Commits are made **under the user's git identity only**. **Never** add `Co-Authored-By` or any AI attribution to commits or PRs.
- Use small commits with imperative messages (`Add retrieval eval dataset`).
- Never commit `.env`, API keys, local DBs or `course/` materials.

## 7. Repository map (keep updated)

```
CLAUDE.md                     agent instructions (this file)
.claude/skills/               reusable workflows (crisp-dm-step, add-component, build-eval-dataset, run-evals)
docs/                         crisp-dm.md (phase log), architecture.md, course-notes.md, report
data/policies/                policy corpus (markdown, numbered sections)
data/README.md                data card: sources, generation method, statistics
src/hr_assistant/
  config.py                   settings from .env (single source)
  llm.py                      LLM client wrapper + tracer (all model calls go here)
  schemas.py                  Pydantic models for structured LLM outputs
  prompts/<component>.md      one prompt file per LLM component
  components/<component>.py   guard, router, collector, rewriter, retriever, reranker, answerer, leave_agent, referral
  tools/                      tool schemas + implementations (the only DB access)
  rules.py                    deterministic leave rule engine
  db.py                       SQLite schema + seed
  pipeline.py                 orchestration: one message in → reply + trace out
evals/datasets/<component>.jsonl   gold data, each row has "split": "dev" | "test"
evals/run_<component>.py      eval script per component
evals/results/<component>.json     metrics + model + date + git commit
tests/                        pytest unit tests (rules, tools, chunking)
app/streamlit_app.py          UI entry point
```
