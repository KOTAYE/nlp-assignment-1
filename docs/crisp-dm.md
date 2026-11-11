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

### 1.4 Leave business rules [confirmed, refined in Data Preparation]
These rules are deterministic and are checked in code (`rules.py`). The LLM only collects the inputs, calls the tool and explains the decision. The **policy corpus is the source of truth** (`leave-policy §3.3, §4.2, §5.2`, `sick-leave-policy §2.4`).

| Leave type | Allowance | Auto-decision |
|---|---|---|
| Annual | 24 working days / year; 2 days per full month in the first year; carry-over ≤ 5 days, valid until 31 March | **approve** if balance is sufficient + notice met (≥ 14 calendar days for > 3 working days, ≥ 2 working days otherwise) + no overlap with own requests; **decline** if any of these fails; **pending_hr** if ≥ 2 teammates already have approved leave on any requested day |
| Sick | ≤ 3 consecutive working days without a certificate; 10 paid days / year | **approve** if ≤ 3 days and the yearly total stays ≤ 10; **pending_hr** otherwise; never declined for notice |
| Unpaid | ≤ 20 working days / year | **pending_hr** (manager approval); **decline** if the yearly limit would be exceeded |
| Special (wedding, bereavement, childbirth) | 3 working days per event | **approve** if within the limit; **pending_hr** otherwise |
| Any type, contractor | not covered (`leave-policy §1.2`, `sick-leave-policy §1.1`) | **decline** with an explanation |

Working days exclude weekends and company holidays (`leave-policy §6.1`). The arithmetic is done in code.

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
### 2.1 Survey of existing data (2026-11-12)
| Source | What it is | License | Verdict |
|---|---|---|---|
| [syncora/hr-policies-qa-dataset](https://huggingface.co/datasets/syncora/hr-policies-qa-dataset) (HF) | 644 synthetic chat Q&A pairs about generic HR policy | MIT | **Partial reuse.** Answers are not grounded in any document, so it is useless as a corpus or as answer gold. Its **questions** are realistic employee phrasing → sampled as router inputs and as out-of-scope probes for HR referral, **relabelled by hand** against our corpus. |
| [opengovfoundation/hr-manual](https://github.com/opengovfoundation/hr-manual) (GitHub) | Real HR policy manual of a non-profit, markdown, ~2.9k words | CC0-1.0 | **Structural reference.** Gives a realistic section structure (conduct, benefits, reimbursements, vacation, sick days). Its wording may be adapted (public domain), but its rules are too thin and unconditional for our clarification use case. |
| Other HF sets (adarsh-08/hr-policy-dataset, EmbraceCoder/HR_Policy, ai-training-datasets/hr) | Small instruction / chat sets | various | Rejected: not document-grounded, no section IDs. |
| IEEE DataPort "RAG pipeline evaluation" | Employee data + policy docs | subscription | Rejected: not openly accessible. |
| Kaggle | — | — | No relevant HR-policy corpus found. |

### 2.2 Decision
No open dataset provides **a policy corpus + questions with gold section IDs + conditional rules + leave records**, and our evals need all of these. Therefore:
1. **Policy corpus:** synthetic *Lumora Tech* policies, written for this project. The structure follows the OpenGov manual. Rules are deliberately conditional (employment type, tenure, location), and every section has a stable ID (`leave-policy §3.4`).
2. **Employee and leave DB:** synthetic seed (~30 employees across teams, types and tenures, plus existing leave requests that create overlap and balance edge cases).
3. **Eval questions:** a mix of hand-written questions, LLM-drafted questions checked by hand, and **sampled syncora questions** (realistic phrasing; many are out of scope for our corpus, so they make good HR-referral probes).

### 2.3 Data risks
- Synthetic corpus is cleaner than real handbooks. Mitigation: add some realistic noise (cross-references, exceptions, a table, one outdated-version note).
- Questions written by the same author as the corpus may overlap lexically with it, which inflates BM25. Mitigation: syncora phrasing, paraphrase rows, and a check of the lexical-overlap distribution.

## 3. Data Preparation

### 3.1 Policy corpus (2026-11-12)
- 9 markdown documents in `data/policies/`, **98 numbered sections**, ~4,000 words. See the data card in `data/README.md`.
- Each document has front matter (`doc_id`, version, effective date). Each `### N.M` heading is a citable section (`leave-policy §3.4`).
- Designed for the evals:
  - **Conditional rules** (employment type × probation × location) make clarification necessary.
  - **Cross-references** between documents make multi-hop questions possible.
  - **Tables** (benefits matrix, holidays, special leave) test structure-preserving chunking.
  - An **outdated-version note** (carry-over of 10 → 5 days) is a hallucination trap.
  - **Explicit "handled by HR" sections** (maternity, harassment, stays abroad > 30 days, salary/promotion) give gold labels for HR referral.

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
| 2 | 2026-11-12 | Data Understanding | Surveyed HF/GitHub/Kaggle; decided synthetic corpus + reuse of syncora questions + OpenGov structure | — |
| 3 | 2026-11-12 | Data Preparation | Wrote 9-document policy corpus (98 sections); refined leave rules to match corpus (notice → decline, sick yearly cap, contractors declined) | — |
