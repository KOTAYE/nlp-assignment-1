# Course notes (UCU NLP) condensed for this project

A short reference distilled from the course lectures so the agent can use the course's terminology and recommended practice **without loading the full slides**. The source lectures live in `course/` (local only, not in git). Each bullet notes the lecture it comes from.

## 1. Lifecycle
- **CRISP-DM** is the course's lifecycle (Lecture 1): Business Understanding → Data Understanding → Data Preparation → Modeling → Evaluation → Deployment, iterative. The lecture's practical loop is *Define problem → Collect → Annotate → Clean → Model → Evaluate → Deploy → Monitor*.
- **Text cleaning** checklist (Lecture 1): normalisation, removing HTML/URLs, duplicates, typos, code-switching. Apply the same normalisation to the **query** as to the documents (IR lecture).

## 2. Evaluation vocabulary (Lecture 2, Evaluation in NLP)
- "We cannot improve what we cannot measure." Evaluating means comparing outputs against a **gold standard / answer key**.
- **Intrinsic** evaluation (does the component work in isolation?) vs **extrinsic** evaluation (does it help the end-to-end task?). We need **both**: per-component intrinsic metrics plus end-to-end extrinsic scenarios.
- Use a **holdout** split. From the RAG lecture: *tune prompts on a dev set, report on a separate test set*.
- **Classification:** accuracy (misleading on imbalanced data), **confusion matrix**, precision / recall / **F1**, **MCC** (robust on imbalanced data and independent of which class is "positive"), macro / micro / weighted averages for multi-class. Precision–recall beats ROC when classes are imbalanced or error costs are asymmetric.
  - For us, a missed HR referral (FN) costs more than an unnecessary one (FP), so report **recall on the "route to HR" class**.
- **Generation:** BLEU (precision, n-grams), ROUGE (recall, coverage), METEOR, **BERTScore** (semantic), COMET. **Model-as-a-Judge** is semantic and explainable, but non-deterministic and costly, so *"we need a benchmark for the judge"*. Calibrate the judge on a small human-labelled sample.
- Takeaways: no one-size-fits-all metric; align metrics with business objectives; "the evaluation metric is a proxy for the real world".

## 3. Retrieval (Lecture 3 IR + RAG lecture)
- Building blocks: corpus/document/query, tokenisation, normalisation, stopwords, stemming/lemmatisation, inverted index.
- **Sparse** (TF-IDF, **BM25**) vs **dense** (embeddings, cosine) vs **hybrid** retrieval. ANN indexes (HNSW, LSH) are for scale. Late interaction (ColBERT) and **rerankers** (cross-encoder; Jina/Qwen reranker): *"a reranker cannot bring a missing candidate back"*.
- **Retrieval metrics:** Precision, Recall, **P@k**, **Hit@k**, AP/**MAP**, **MRR**, **nDCG@k**. *"Metrics should be designed according to the goals of the system."*
- **Chunking:** fixed-size (paragraph-packed, with overlap), semantic (section-aware), recursive. **Keep metadata** (document title, section heading, version/date), because a value without its row/section is useless (the Docling example).
- **Failure-stage thinking:** Parse → Chunk → Retrieve → Rank → Assemble context. *"Find the first stage that loses required evidence before changing the prompt."*
- **Improving RAG:** query rewrite, multi-query plus **Reciprocal Rank Fusion (RRF)**, question decomposition, **HyDE**, **routing** between sources, better chunking and indexing.
- **Routing:** the slides use an "HR policy" source example. Pick the access method per source: policy docs → retrieval, current state (orders / *leave requests*) → database/API. A router can be rule-based, LLM-based or a trained classifier (LogisticRegression on embeddings). Test paraphrases, negation and mixed intents separately.
- **Access-controlled retrieval:** the application enforces permissions *before* content can reach the model context (an employee sees only their own leave requests).

## 4. RAG evaluation (RAG lecture: RAGAS / DeepEval)
- *"Measure retrieval and generation separately. Use controlled examples before trusting an LLM judge."*
- Retrieval side: **Context Precision** (relevant chunks ranked high) and **Context Recall** (all needed evidence retrieved). The deterministic versions are Hit@k / Recall@k / MRR against gold chunk IDs.
- Generation side: **Faithfulness** = supported claims / total claims (the "fake news metric") and **Answer Relevancy**.
- Tools: **RAGAS**, **DeepEval**. Embeddings: Sentence Transformers. Index: FAISS / pgvector / Qdrant.

## 5. Prompting (RAG lecture, first part)
- Prompt frameworks (R.O.S.E.S., ICIO, CRISPE…): specify task, audience, context and **output contract** (format).
- Sampling: temperature, top-p/top-k. Use low temperature for extraction, classification and tool calls.
- Few-shot biases (majority-label, recency, common-token) and their fixes: over-sampling, shuffling, paraphrasing.
- CoT / Program-of-Thought: delegate computation (for example *leave-day arithmetic*) to code, not to the model.
- **Prompt evaluation process:** fix the task, model settings and eval cases → change **one prompt factor** → inspect failures → record prompt version, raw outputs, failed cases and the final test result.

## 6. Agents (AI Agents lecture)
- An agent is a **policy in a loop**: decide → act → observe → terminate. *"If your code decides, it is a workflow."* **Autonomy is a cost**, so use the lowest level that solves the task.
- **Tools are typed contracts:** the description *is* the prompt; **enums beat free text**; defaults; small return shapes; **instructive errors** (`retryable`, `hint`); least privilege. *"Never regex-parse tool calls"*: use native function calling.
- **Control policy:** max steps, cost cap, repeated-call detection, **confirmation gates for irreversible actions** (approving or declining leave = human-in-the-loop).
- **Observability:** log messages, tool name/args/latency, tokens, **stop reason** per run.
- **Agentic retrieval:** retrieval becomes a tool the model calls and can retry. "Watch for over-retrieval."
- **Skills** = procedural memory (`SKILL.md` with name + description, progressive disclosure). Improve the environment before the model.
- **Agent evaluation:** evaluate the **trajectory, not just the answer**, in layers:
  - **Outcome**: programmatic checks such as DB state or exact match.
  - **Process**: right tools, no redundant calls.
  - **Efficiency**: steps, tokens, cost per completed task.
  - **Safety**: no writes outside scope, confirmations honoured.
  - **Communication**: citations resolve, escalation is legible.
  - The rule is *"Assertions beat judges: what can be code should be code."* Minimum: **20–50 tasks with automatic checks**.
  - **pass^k** measures consistency across repeated runs (τ-bench: policy-constrained tool use with a simulated user, the closest benchmark to our HR assistant).
- **Security:** prompt injection via retrieved documents; the "lethal trifecta" (private data + untrusted content + exfiltration path).

## 7. Ethics and guardrails (Ethics lecture)
- **Guardrails:** input guards (privacy/PII) → LLM → output guards (toxicity, **hallucination**, data leakage, bias).
- Bias/fairness evaluation exists (BBQ, StereoSet, WinoBias). For HR, check that answers and leave decisions do not depend on protected attributes. This is optional scope.
- Jailbreak families: role override, refusal suppression, format laundering. Worth a small red-team slice in the evals.

## 8. How this maps onto our components

| Our component | Course terms / metrics to use |
|---|---|
| Intent router (policy Q / leave request / out-of-scope) | classification: confusion matrix, macro-F1, recall on the HR-referral class |
| Information collection (slot filling, clarifying questions) | slot-level precision/recall/F1, "asked when needed" rate |
| Retrieval over policies | Hit@k, Recall@k, MRR (deterministic, gold chunk IDs) + Context Precision/Recall |
| Answer generation with citations | Faithfulness, Answer Relevancy, citation accuracy (cited section ∈ gold) |
| HR referral / abstention | precision/recall/F1 on "should route to HR" |
| Leave-request agent (DB via tools) | outcome (DB state assertions), process (correct tool sequence), safety (confirmation gate), pass^k |
| End-to-end | extrinsic scenario suite, 20–50 tasks, success rate split by stop reason |
