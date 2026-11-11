# HR Assistant: an NLP system for Lumora Tech

NLP course, Assignment 1: *Build an NLP System*. Topic: **HR assistant**.

The assistant answers employee questions about HR procedures. It works only from company policy and **cites the exact policy section** in every answer. When the answer depends on facts it does not know yet, it **asks a clarifying question** first. Employees can **request, track and cancel leave**: the leave **database is accessed only through LLM tool calls**, and leave decisions come from transparent rules. Anything the policies do not support is **routed to HR** as a ticket. Every component has its own evaluation.

> Company, policies and employees are fictional, created for this project.

| Document | What it contains |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Data-flow diagram (LLM calls and tool calls marked), purpose / input / output of each component, walkthrough of one input |
| [docs/crisp-dm.md](docs/crisp-dm.md) | CRISP-DM log: business understanding, scope and business rules, data, modeling, evaluation, deployment, iteration log |
| [docs/report.md](docs/report.md) | **Report** with all evaluation results and their interpretation (PDF: [docs/report.pdf](docs/report.pdf)) |
| [docs/requirements-traceability.md](docs/requirements-traceability.md) | Every requirement of the assignment brief mapped to an artifact |
| [CLAUDE.md](CLAUDE.md), [.claude/skills/](.claude/skills/) | How the AI coding agent was steered: rules, CRISP-DM process, conventions, skills |
| [data/README.md](data/README.md) | Data card: policy corpus, employee/leave seed, external data used |

## Quick start

Requirements: Python 3.12, an OpenRouter API key (any OpenAI-compatible endpoint works).

```bash
git clone https://github.com/KOTAYE/nlp-assignment-1.git
cd nlp-assignment-1
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env            # Linux/macOS: cp .env.example .env  — then put your key into .env
```

`.env`:
```
LLM_API_KEY=sk-or-v1-...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
JUDGE_MODEL=google/gemini-2.5-flash     # used only by evals
HR_TODAY=2026-11-12                     # optional: fixed business date for a reproducible demo
```

### Run the app
```bash
streamlit run app/streamlit_app.py
```
Pick an employee in the sidebar ("log in as"). Try:
- *How many vacation days can I carry over?* → answer with citation
- *Do I need a sick note?* → clarifying question → answer
- *Book annual leave 7–11 December* · *How many days do I have left?* · *Cancel it* → leave agent with DB tools
- *What is the salary range for a senior engineer?* → HR ticket
- log in as **Olena Hrytsenko (HR)**: *Show pending requests* → *Approve #8* → *Yes, confirm*

Turn on **Show trace** to see every LLM call and tool call (with prompt version, tokens, latency, cost) for each message. All traces are also written to `logs/traces/*.jsonl`.

To reset the demo data: `python scripts/reset_db.py`.

### Run tests and evaluations
```bash
pytest                                   # 54 unit tests (rule engine, tools, guard, chunker)
python -m evals.build_datasets           # rebuild gold datasets (deterministic)
python -m evals.run_all --split test     # every component eval on the test split (~5 min, ~$0.10)
python -m evals.run_qa --split dev       # or a single component on the dev split
```
Results are saved to `evals/results/<component>__<variant>__<split>.json`, together with model names, prompt versions, date and git commit.

## System at a glance

```
message → guard → router ─┬─ policy_question → collector (clarify?) → rewriter → hybrid retrieval (BM25+dense, RRF)
                          │                     → cross-encoder rerank → grounded answerer (citations, sufficiency)
                          │                                                     └─ insufficient → HR referral (LLM → create_hr_ticket)
                          ├─ leave_action ───→ leave agent (LLM + tools → rule engine → SQLite)
                          ├─ hr_referral ────→ HR referral (LLM → create_hr_ticket)
                          └─ smalltalk / unclear → canned reply
```
See [docs/architecture.md](docs/architecture.md) for the full diagram.

## Repository layout
```
src/hr_assistant/   config, llm (client + tracing), schemas, prompts/, components/, tools, rules, db, directory, retrieval, pipeline
app/                Streamlit UI
data/policies/      policy corpus (9 documents, 98 sections)
evals/              datasets/, run_*.py, results/
tests/              unit tests
docs/               architecture, CRISP-DM log, report, traceability, course notes
```
