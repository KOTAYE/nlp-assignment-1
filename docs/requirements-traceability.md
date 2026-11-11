# Requirements traceability: assignment brief → project artifacts

The assignment brief (*NLP Assignment 1. Build an NLP System*) is the **highest-priority source of requirements**. Every requirement is quoted (or closely paraphrased) below and mapped to where it is satisfied.
Status: ✅ done · 🟡 in progress / planned with a concrete artifact · ⬜ not started.

## A. Objective
| ID | Requirement (brief) | Where it is satisfied | Status |
|---|---|---|---|
| A1 | Build a small NLP system with an AI coding assistant | Whole repo; workflow in `CLAUDE.md` | 🟡 |
| A2 | Think through how you manage the assistant: what goes into its context | `CLAUDE.md` §3 (context hygiene), `docs/course-notes.md` (condensed context), lectures kept out of context in `course/` | ✅ |
| A3 | Agents / convention file to control code quality | `CLAUDE.md` §4 (conventions); enforced by `ruff` + `pytest` config in `pyproject.toml` | 🟡 |
| A4 | Be ready to explain how the system works; purpose of each component | `docs/architecture.md` (diagram, component table, walkthrough) | ✅ |
| A5 | Evaluate output quality, **at each stage** if there are multiple components | `docs/architecture.md` eval column (every component, incl. indexer, rule engine, tracer, E2E); `evals/` | 🟡 |

## B. Task
| ID | Requirement | Where | Status |
|---|---|---|---|
| B1 | Working prototype that accepts input and produces useful output | `app/streamlit_app.py` + `src/hr_assistant/pipeline.py` | ⬜ |
| B2 | Select tools, model, interface (simple web UI is fine) | `docs/crisp-dm.md` §1.7: gpt-4o-mini via OpenRouter, local BM25 + embeddings + reranker, Streamlit | ✅ |
| B3 | App must be possible to run (for the demo video) | `README.md` setup and run instructions | ⬜ |
| B4 | Follow the CRISP-DM cycle, reflected in the report | `docs/crisp-dm.md` (phase log + iteration log) → report | 🟡 |
| B5 | Create SKILLS for the agentic development flow | `.claude/skills/` (crisp-dm-step, add-component, build-eval-dataset, run-evals) | ✅ |
| B6 | Not vanilla RAG | `docs/architecture.md` "Why not vanilla RAG" | ✅ (design) |

## C. HR assistant requirements (project example chosen)
| ID | Requirement | Where | Status |
|---|---|---|---|
| C1 | Answers employee questions about HR procedures: leave, onboarding, benefits, internal requests | `data/policies/` (leave, sick leave, onboarding, benefits, internal requests, remote work, expenses, equipment, conduct) | ✅ (data) |
| C2 | Small collection of company policies (fictional allowed) | 9 docs, 98 sections; `data/README.md` | ✅ |
| C3 | **Collect the information needed** to answer each question | Info collector (component 3) | ⬜ |
| C4 | **Retrieve the relevant policy and identify the source** in the answer | Retriever + reranker + grounded answerer with citations (4a–5) | ⬜ |
| C5 | Employee requests a leave (any type, defined by us) | Leave agent + `submit_leave` tool; leave types in `docs/crisp-dm.md` §1.4 | ⬜ |
| C6 | System **tracks** it (approve / decline) | `leave_requests` table with status; rule engine; `decide_leave` for HR | ⬜ |
| C7 | **Use a database**, **access it via LLM only** | SQLite reachable only through LLM tool calls (leave agent tools, `create_hr_ticket`); see the database access rule in `docs/architecture.md` | ⬜ |
| C8 | If the policies do not support an answer, **route to HR** | Sufficiency flag → HR referral (LLM + `create_hr_ticket`) | ⬜ |
| C9 | Evaluate each component | `evals/run_<component>.py` for every row of the component table | ⬜ |
| C10 | Report metrics for **information collection** | Collector: slot P/R/F1, clarification P/R | ⬜ |
| C11 | Report metrics for **retrieval success** | Hit@k, Recall@k, MRR (+ nDCG@5 for reranker) | ⬜ |
| C12 | Report metrics for **answer correctness** | Calibrated LLM-judge correctness vs gold answers | ⬜ |
| C13 | Report metrics for **source support** | Faithfulness + citation accuracy | ⬜ |
| C14 | Report metrics for **correct referral to HR** | Referral precision / recall / F1 | ⬜ |

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
| D9 | Evaluation for **every component** (an LLM judge is allowed) | `evals/`, judge calibration per `run-evals` skill | ⬜ |
| D10 | Distinguish high vs low scores, explain why scores are not higher, propose improvements | `run-evals` skill → `docs/crisp-dm.md` §5 interpretation per metric | ⬜ |
| D11 | **Metric selection will be judged**: choose proper metrics | `docs/crisp-dm.md` §5 "Why this metric" for every metric | ⬜ |

## E. Submission
| ID | Requirement | Where | Status |
|---|---|---|---|
| E1 | Code (or notebook) with **setup and run instructions**; GitHub is fine | https://github.com/KOTAYE/nlp-assignment-1, `README.md` | 🟡 |
| E2 | **High-level system diagrams** | `docs/architecture.md` | ✅ |
| E3 | **Description of the business logic kept in scope** | `docs/crisp-dm.md` §1 | ✅ |
| E4 | **Eval results**, in a **PDF or a notebook** | `docs/report.md` → exported `docs/report.pdf`, plus `evals/results/*.json` | ⬜ |
| E5 | Video ≤ 10 min showing report docs, diagrams and a running demo | `docs/demo-script.md` (timed outline) | ⬜ |
| E5a | — talk about the system requirements selected for the scope | demo script §1 ← `docs/crisp-dm.md` §1 | ⬜ |
| E5b | — talk about the components (diagram) and **why they were selected** | demo script §2 ← `docs/architecture.md` "Why" | ⬜ |
| E5c | — run the app through several cases (LLM tracing optional) | demo script §3; trace panel in the UI | ⬜ |
| E5d | — show and explain the evaluations | demo script §4 ← report | ⬜ |
| E5e | — show the agentic coding env: context, behaviour control | demo script §5 ← `CLAUDE.md`, skills, this file | ⬜ |

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
