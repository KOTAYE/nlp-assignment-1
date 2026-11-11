"""Component 2: intent router (LLM with structured output) + a classical baseline for comparison."""

from __future__ import annotations

from ..llm import complete_json
from ..schemas import RouteResult


def _format_history(history: list[dict], turns: int = 4) -> str:
    recent = history[-turns:]
    return "\n".join(f"{m['role']}: {m['content']}" for m in recent) or "(none)"


def route(message: str, history: list[dict] | None = None) -> RouteResult:
    user = f"Conversation so far:\n{_format_history(history or [])}\n\nLatest message:\n{message}"
    return complete_json("router", "router", user, RouteResult)


class TfidfLogRegRouter:
    """Classical baseline (Lecture 1 / Classical NLP): TF-IDF word+char n-grams + logistic regression.
    Trained on the dev split only; compared with the LLM router on the test split."""

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline, make_union

        self.model = make_pipeline(
            make_union(
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
                TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True),
            ),
            LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced"),
        )

    def fit(self, texts: list[str], labels: list[str]) -> TfidfLogRegRouter:
        self.model.fit(texts, labels)
        return self

    def predict(self, texts: list[str]) -> list[str]:
        return list(self.model.predict(texts))
