# CRISP-DM log — HR Assistant

This is a living document. Each phase records its decisions, and every iteration records what changed and the metric before → after.
Status labels: **[confirmed]** = agreed with the project owner, **[proposed]** = draft awaiting confirmation.

---

## 1. Business Understanding

### 1.1 Business problem
In a mid-size company, HR receives many repetitive questions (How many vacation days do I have? Do I need a sick note? How do I get reimbursed for a course?) and handles leave requests by hand. Employees wait for answers, and HR loses time on questions the policies already answer.

**Goal:** a self-service assistant that
1. answers HR questions **from company policy only**, with a **citation** to the exact policy section;
2. **asks clarifying questions** when the answer depends on facts it does not yet know;
3. lets employees **file and track leave requests**, decided by transparent business rules and stored in a database reachable **only through the LLM's tools**;
4. **routes to HR** (creates a ticket) when the policies do not cover the question, instead of guessing.

### 1.2 Fictional setting [confirmed]
- **Company:** *Lumora Tech*, a fictional IT company with ~250 employees and offices in Lviv and Kyiv plus remote staff.
- **Corpus:** 8–10 policy documents with numbered sections: Leave, Sick Leave, Remote Work, Onboarding, Benefits (health, sport, education budget), Expense Reimbursement, Equipment, Code of Conduct, Internal Requests.
- **Policies are deliberately conditional**, so that collecting information is actually needed. Answers depend on **employment type** (full-time / part-time / contractor), **tenure**, and sometimes **office location**.
- **Language:** English for the corpus, UI, answers and code. [confirmed]

### 1.3 Users and use cases
| Actor | Use case |
|---|---|
| Employee | Ask a policy question → get an answer with a source, or a clarifying question first |
| Employee | Request leave (annual / sick / unpaid / special) → get an immediate decision with a reason |
| Employee | Check leave balance and the status of their requests; cancel a pending request |
| Employee | Ask something the policies do not cover → the question is routed to HR with a ticket ID |
| HR manager | Review requests the rules left in `pending_hr`; approve or decline through the chat (tools) |

### 1.4 Leave business rules [confirmed]
These are deterministic, so they are checked in code. The LLM collects the inputs, calls the tool, and explains the decision.

| Leave type | Allowance | Auto-decision |
|---|---|---|
| Annual | 24 working days / year (pro-rated in the first year; contractors are not eligible) | **approve** if balance is sufficient, notice ≥ 14 days for > 3 days of leave (≥ 2 days otherwise), and no overlap with the employee's own requests; **decline** if balance is insufficient or the employee is ineligible; **pending_hr** if ≥ 2 teammates are already off on those dates |
| Sick | Up to 3 consecutive days without a certificate; 10 paid days / year | **approve** if ≤ 3 days; **pending_hr** if > 3 days (certificate required) |
| Unpaid | Up to 20 days / year | always **pending_hr** (requires manager approval) |
| Special (wedding, bereavement, childbirth) | 3 days per event | **approve** if within the limit; **pending_hr** otherwise |

Working-day arithmetic is done in code (weekends and public holidays from a fixed calendar), never by the LLM.

### 1.5 Scope
**In scope:** policy Q&A with citations; clarification; leave CRUD with rule-based decisions; HR referral tickets; HR-manager decision flow; tracing; per-component evals; a local web UI.
**Out of scope:** real authentication (the UI has a "log in as" employee selector), payroll, email notifications, multi-tenant deployment, document uploads (sick certificates are simulated as a yes/no flag).

### 1.6 Success criteria (targets for the test set) [proposed]
| Area (from the brief) | Metric | Target |
|---|---|---|
| Intent routing | macro-F1 / MCC; recall on `out_of_scope` | ≥ 0.90 / ≥ 0.85; ≥ 0.95 |
| Information collection | slot F1; clarification precision/recall ("asked iff needed") | ≥ 0.90; ≥ 0.85 |
| Retrieval success | Hit@5, Recall@5, MRR (gold section IDs) | ≥ 0.90, ≥ 0.85, ≥ 0.75 |
| Answer correctness | LLM-judge correctness vs gold answer (calibrated rubric) | ≥ 0.85 |
| Source support | Faithfulness; citation accuracy (cited section ∈ gold) | ≥ 0.90; ≥ 0.90 |
| Correct referral to HR | precision / recall on "should route to HR" | ≥ 0.85 / ≥ 0.95 |
| Leave agent | DB-state outcome accuracy; correct tool sequence; pass^3 | ≥ 0.90; ≥ 0.85; ≥ 0.80 |
| End-to-end | scenario success rate (30+ scripted scenarios) | ≥ 0.85 |

Recall on HR referral matters more than precision. A wrong confident answer about benefits or leave costs more than an unnecessary ticket.

### 1.7 Resources and constraints
- LLM: `openai/gpt-4o-mini` via OpenRouter ($2.30 budget limit on the key). A stronger model is used only as the judge, if calibration shows it is needed.
- Retrieval runs locally (BM25 + Sentence-Transformers embeddings), so it needs no API cost.
- UI: Streamlit (chat + employee selector + trace panel). [confirmed]
- Components: the full set from `docs/architecture.md`. [confirmed]
- Deliverables: GitHub repo, report, diagrams, eval results, ≤ 10-minute demo video.

---

## 2. Data Understanding
_TODO: survey existing HR-policy / HR-QA datasets first, then decide whether to adapt or generate synthetic data._

## 3. Data Preparation
_TODO_

## 4. Modeling
_TODO — see `docs/architecture.md` for the component design._

## 5. Evaluation
_TODO_

## 6. Deployment
_TODO_

---

## Iteration log
| # | Date | Phase | Change | Metric before → after |
|---|---|---|---|---|
| 0 | 2026-11-12 | Business Understanding | Initial scope draft | — |
| 1 | 2026-11-12 | Business Understanding | Owner confirmed language (EN), leave rules, full component set, Streamlit UI | — |
