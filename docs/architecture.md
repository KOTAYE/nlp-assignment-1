# Architecture — HR Assistant [proposed]

## Data flow

```mermaid
flowchart TD
    U([Employee / HR manager<br/>Streamlit chat]) --> G[1. Input guard<br/>rules: length, PII mask, injection patterns]
    G --> R{2. Intent router<br/>LLM structured output<br/>baseline: TF-IDF + LogReg}

    R -->|policy_question| C1[3. Info collector<br/>slot filling: employment type,<br/>tenure, location]
    R -->|leave_action| A[6. Leave agent<br/>LLM + native tool calling]
    R -->|out_of_scope / sensitive| H[7. HR referral<br/>create_hr_ticket]
    R -->|unclear| Q[Clarifying question]

    C1 -->|missing slot| Q
    C1 -->|slots complete| QR[4a. Query rewriter<br/>LLM: standalone query]
    QR --> RET[4b. Hybrid retriever<br/>BM25 + dense embeddings<br/>Reciprocal Rank Fusion]
    RET --> RR[4c. Reranker<br/>cross-encoder, top-k]
    RR --> GEN[5. Grounded answerer<br/>LLM: answer + citations +<br/>sufficiency flag]
    GEN -->|insufficient evidence| H
    GEN -->|supported| OUT([Answer with sources])

    A <-->|tools| T[[Tool layer<br/>get_balance · list_requests ·<br/>submit_leave · cancel_leave ·<br/>decide_leave HR only]]
    T <--> RULES[Rule engine<br/>working days, balance,<br/>notice, overlap]
    T <--> DB[(SQLite<br/>employees · leave_requests ·<br/>hr_tickets)]
    H --> DB
    A --> OUT
    H --> OUT
    Q --> U

    POL[(Policy corpus<br/>markdown, sectioned)] --> IDX[Indexer<br/>section-aware chunking<br/>+ metadata] --> RET

    TR[/Tracer: every LLM & tool call<br/>component · prompt · output · tokens · latency/]
    R -.-> TR
    QR -.-> TR
    GEN -.-> TR
    A -.-> TR
```

## Components

| # | Component | Purpose | Input → Output | Model / tool calls | Eval |
|---|---|---|---|---|---|
| 1 | Input guard | Block injection attempts, mask PII before it reaches the LLM | raw text → clean text / block | none (rules) | red-team slice: block rate, false-block rate |
| 2 | Intent router | Pick the processing path | message + short history → `{intent, confidence}` | **LLM** (JSON schema); classical baseline for comparison | confusion matrix, macro-F1, MCC, recall(out_of_scope) |
| 3 | Info collector | Detect which facts a question depends on and ask for missing ones | question + employee profile → slots / clarifying question | **LLM** (JSON schema) | slot P/R/F1, clarification precision/recall |
| 4a | Query rewriter | Turn a conversational turn into a standalone search query | history + question → query | **LLM** | measured indirectly via retrieval (with vs without rewriting) |
| 4b | Hybrid retriever | Find candidate policy sections | query → top-20 chunks | BM25 + Sentence-Transformers (local) | Hit@k, Recall@k, MRR: BM25 vs dense vs hybrid |
| 4c | Reranker | Reorder candidates precisely | query + 20 chunks → top-5 | cross-encoder (local) | MRR / nDCG@5 before vs after |
| 5 | Grounded answerer | Answer only from evidence, cite sections, flag insufficiency | query + slots + top-5 → `{answer, citations[], sufficient}` | **LLM** (JSON schema) | correctness (judge), Faithfulness, citation accuracy |
| 6 | Leave agent | Run leave actions through tools | message + employee → tool calls → reply | **LLM** + **tools** | DB-state outcome, tool-sequence correctness, pass^k |
| 7 | HR referral | Escalate unsupported or sensitive questions | question → ticket ID | **tool** `create_hr_ticket` | referral precision/recall |
| — | Rule engine | Deterministic leave decisions | request + DB state → approve / decline / pending_hr + reason | none (code) | unit tests (100% expected) |
| — | Tracer | Observability for the demo and debugging | every call → JSONL trace | none | — |

## Why not vanilla RAG
- **Routing** sends each message to the right source: documents → retrieval, live state → DB tools, unknown → human.
- **Clarification** happens before retrieval, because the policies are conditional.
- **Hybrid retrieval + reranking**, compared against single-method baselines.
- **Abstention → HR ticket** instead of hallucinating.
- **Agent with tools** over a database, with a deterministic rule engine and a confirmation gate for HR decisions.

## Walkthrough: one input through the system
*"How many vacation days can I carry over to next year?"* asked by a contractor:
1. **Guard** passes the text.
2. **Router** classifies it as `policy_question`.
3. **Collector** finds that carry-over depends on employment type. The type is already known from the profile (`contractor`), so no question is asked.
4. **Rewriter** produces "annual leave carry-over rules for contractors". **Retriever** runs BM25 + dense search and fuses the results with RRF. **Reranker** returns the top-5, with `leave-policy §1.2` (eligibility) and `§3.4` (carry-over) at the top.
5. **Answerer** replies: "Contractors are not covered by the annual leave policy, so carry-over does not apply [Leave Policy §1.2]", with `sufficient = true`.
6. The **Tracer** has logged 3 LLM calls with their tokens and latency. The UI shows the trace panel.
