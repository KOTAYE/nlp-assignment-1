# Requirements traceability: assignment brief → project artifacts

The assignment brief (*NLP Assignment 1. Build an NLP System*) is the **highest-priority source of requirements**. Every requirement is quoted (or closely paraphrased) below and mapped to where it is satisfied.
Status: ✅ done · 🟡 in progress / planned with a concrete artifact · ⬜ not started.

## A. Objective
| ID | Requirement (brief) | Where it is satisfied | Status |
|---|---|---|---|
| A1 | Build a small NLP system with an AI coding assistant | Whole repo; workflow in `CLAUDE.md` | ✅ |
| A2 | Think through how you manage the assistant: what goes into its context | `CLAUDE.md` §3 (context hygiene), `docs/course-notes.md` (condensed context), lectures kept out of context in `course/` | ✅ |
| A3 | Agents / convention file to control code quality | `CLAUDE.md` §4 (conventions); enforced by `ruff` (lint + format) and `pytest` configured in `pyproject.toml` | ✅ |
| A4 | Be ready to explain how the system works; purpose of each component | `docs/architecture.md` (diagram, component table, walkthrough) | ✅ |
| A5 | Evaluate output quality, **at each stage** if there are multiple components | Every component has an eval (`evals/run_*.py`) incl. indexer, rule engine, output guard (verifier), date resolver (unit tests + agent holdout-2 and holdout-4), prompt/eval leakage check, tracer coverage, E2E; results in `docs/report.md` §5 | ✅ |

## B. Task
| ID | Requirement | Where | Status |
|---|---|---|---|
| B1 | Working prototype that accepts input and produces useful output | `app/streamlit_app.py` + `src/hr_assistant/pipeline.py`; UI smoke-tested with Streamlit AppTest; E2E scenarios | ✅ |
| B2 | Select tools, model, interface (simple web UI is fine) | `docs/crisp-dm.md` §1.7: gpt-4o-mini via OpenRouter, local BM25 + embeddings + reranker, Streamlit | ✅ |
| B3 | App must be possible to run (for the demo video) | `README.md` quick start; `scripts/reset_db.py`; `HR_TODAY` for a reproducible demo | ✅ |
| B4 | Follow the CRISP-DM cycle, reflected in the report | `docs/crisp-dm.md` (phase log + 23-row iteration log, five iterations, four holdouts written before their fixes), report §4 | ✅ |
| B5 | Create SKILLS for the agentic development flow | `.claude/skills/` (crisp-dm-step, add-component, build-eval-dataset, run-evals) | ✅ |
| B6 | Not vanilla RAG | `docs/architecture.md` "Why not vanilla RAG" | ✅ (design) |

## C. HR assistant requirements (project example chosen)
| ID | Requirement | Where | Status |
|---|---|---|---|
| C1 | Answers employee questions about HR procedures: leave, onboarding, benefits, internal requests | `data/policies/` (leave, sick leave, onboarding, benefits, internal requests, remote work, expenses, equipment, conduct) | ✅ (data) |
| C2 | Small collection of company policies (fictional allowed) | 9 docs, 98 sections; `data/README.md` | ✅ |
| C3 | **Collect the information needed** to answer each question | Info collector (component 3): profile facts from identity + situational facts, clarifying question, pending-question state in `pipeline.py` | ✅ |
| C4 | **Retrieve the relevant policy and identify the source** in the answer | Hybrid retriever + reranker + grounded answerer; citations validated against the evidence; `with_sources()` guarantees the source appears in the reply text; Sources panel in the UI | ✅ |
| C5 | Employee requests a leave (any type, defined by us) | Leave agent + `submit_leave_request` tool; 4 leave types (annual, sick, unpaid, special) in `docs/crisp-dm.md` §1.4 | ✅ |
| C6 | System **tracks** it (approve / decline) | `leave_requests` table with status (approved / declined / pending_hr / cancelled); rule engine (41/41 tests); `list_my_leave_requests`, `cancel_leave_request`; HR `list_pending_requests` + `decide_leave_request` with confirmation | ✅ |
| C7 | **Use a database**, **access it via LLM only** | SQLite reached only in `tools.py`, which runs only when the LLM requests a tool call (leave agent, referral `create_hr_ticket`). The UI never queries the DB; the profile comes from the identity provider (`directory.py`) | ✅ |
| C8 | If the policies do not support an answer, **route to HR** | Router → `hr_referral` for sensitive topics; answerer `sufficient=false` → referral (LLM + `create_hr_ticket`, ticket ID in the reply) | ✅ |
| C9 | Evaluate each component | `evals/run_<component>.py` for every row of the component table; `docs/eval-results.md` | ✅ |
| C10 | Report metrics for **information collection** | Collector: fact P/R/F1, value extraction, clarification P/R (report §5.3) | ✅ |
| C11 | Report metrics for **retrieval success** | Hit@k, Recall@k, MRR, nDCG for 4 variants + context recall in the pipeline (§5.3–5.4) | ✅ |
| C12 | Report metrics for **answer correctness** | Calibrated 4-level judge vs gold answers; contradiction rate; oracle variant (§5.3) | ✅ |
| C13 | Report metrics for **source support** | Faithfulness (RAGAS definition) + citation hit rate (§5.3) | ✅ |
| C14 | Report metrics for **correct referral to HR** | Referral P/R/F1 + ticket category accuracy (§5.3, §5.5) | ✅ |

## D. Procedure
| ID | Requirement | Where | Status |
|---|---|---|---|
| D1 | Define the task (may extend business requirements if you know how to evaluate them) | `docs/crisp-dm.md` §1; every extension (guard, rewriter, reranker) has its own eval | ✅ |
| D2 | Prepare the data, **checking existing datasets before generating synthetic** | `docs/crisp-dm.md` §2 (survey of HF / GitHub / Kaggle / IEEE, then the decision) | ✅ |
| D3 | Draw a **diagram that shows the data flow** | `docs/architecture.md` (Mermaid) | ✅ |
| D4 | Purpose, input and output of each component | `docs/architecture.md` component table | ✅ |
| D5 | **Identify model calls and external tool calls** | Colour legend in the diagram + "Model / tool calls" column | ✅ |
| D6 | Explain how **one input passes through the complete system** | `docs/architecture.md` walkthrough (+ live trace in the demo) | ✅ (doc) |
| D7 | Manage the coding agent **not only through prompting**: agents md / convention md | `CLAUDE.md`, `.claude/skills/`, this traceability file | ✅ |
| D8 | CRISP-DM instructions placed in the agents md | `CLAUDE.md` §2 | ✅ |
| D9 | Evaluation for **every component** (an LLM judge is allowed) | `evals/`; judge calibrated on controlled examples (§5.4) | ✅ |
| D10 | Distinguish high vs low scores, explain why scores are not higher, propose improvements | Report §5.1 (high/low meaning per metric), §5.5 (first-failing-stage analysis + fixes), §5.6 | ✅ |
| D11 | **Metric selection will be judged**: choose proper metrics | Report §5.1 'Why these metrics' table, grounded in the course lectures | ✅ |

## E. Submission
| ID | Requirement | Where | Status |
|---|---|---|---|
| E1 | Code (or notebook) with **setup and run instructions**; GitHub is fine | https://github.com/KOTAYE/nlp-assignment-1, `README.md` quick start | ✅ |
| E2 | **High-level system diagrams** | `docs/architecture.md` | ✅ |
| E3 | **Description of the business logic kept in scope** | `docs/crisp-dm.md` §1 | ✅ |
| E4 | **Eval results**, in a **PDF or a notebook** | `docs/report.pdf` (exported from `docs/report.md`), `docs/eval-results.md`, `evals/results/*.json` | ✅ |
| E5 | Video ≤ 10 min showing report docs, diagrams and a running demo | `docs/demo-script.md` (timed outline); recording is done by the author | 🟡 |
| E5a | — talk about the system requirements selected for the scope | demo script §1 ← report §1 | 🟡 (author records) |
| E5b | — talk about the components (diagram) and **why they were selected** | demo script §2 ← report §3 | 🟡 (author records) |
| E5c | — run the app through several cases (LLM tracing optional) | demo script §3; trace panel in the UI | 🟡 (author records) |
| E5d | — show and explain the evaluations | demo script §4 ← report §5 | 🟡 (author records) |
| E5e | — show the agentic coding env: context, behaviour control | demo script §5 ← report §6, `CLAUDE.md`, skills | 🟡 (author records) |

## F. Rules
| ID | Requirement | How we comply | Status |
|---|---|---|---|
| F1 | No copying from teammates; same topic → implementation must differ | Original design and corpus; full git history under the author's name | ✅ |
| F2 | Vanilla RAG is not graded | See B6 | ✅ |

## Grading map
| Criterion | Pts | Primary evidence |
|---|---|---|
| System understanding (components + walkthrough) | 4 | `docs/architecture.md`, demo §2–3 |
| Working prototype | 4 | Streamlit app, `README.md` |
| Evaluation of each component | 4 | `evals/`, report §5 |
| Use of the AI coding assistant via md files | 3 | `CLAUDE.md`, `.claude/skills/`, `docs/course-notes.md`, this file |
