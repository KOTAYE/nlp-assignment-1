"""Indexer, sparse/dense/hybrid retrieval, and cross-encoder reranking over the policy corpus.

All local (no API calls). Course references: BM25 and dense retrieval, Reciprocal Rank Fusion (Cormack et al.,
2009), cross-encoder reranking (Nogueira & Cho, 2019), section-aware chunking with metadata (Docling example:
"a value needs its row, column and source").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from .config import get_settings

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
DENSE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RRF_K = 60


@dataclass(frozen=True)
class Chunk:
    id: str  # "<doc_id> §N.M" — the citable section ID
    doc_id: str
    doc_title: str
    section: str  # "N.M"
    heading: str  # "N.M Title"
    parent: str  # "N. Parent title"
    body: str

    @property
    def text(self) -> str:
        """Text that is indexed and shown to the LLM: metadata header + body (keeps tables intact)."""
        return f"[{self.id}] {self.doc_title} > {self.parent} > {self.heading}\n{self.body}"


# ---------------------------------------------------------------- indexer / chunker

_FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)


def parse_document(path: Path) -> list[Chunk]:
    """Section-aware chunking: one chunk per `### N.M` section, with doc title and parent heading as metadata."""
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta = dict(line.split(": ", 1) for line in _FRONT.match(raw).group(1).splitlines())
    body = _FRONT.sub("", raw)
    chunks: list[Chunk] = []
    parent = ""
    current: tuple[str, str] | None = None
    lines: list[str] = []

    def flush() -> None:
        if current:
            sec, title = current
            chunks.append(
                Chunk(
                    f"{meta['doc_id']} §{sec}",
                    meta["doc_id"],
                    meta["title"],
                    sec,
                    f"{sec} {title}",
                    parent,
                    "\n".join(lines).strip(),
                )
            )

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            current, lines = None, []
            parent = line[3:].strip()
        elif m := re.match(r"^### (\d+\.\d+) (.+)$", line):
            flush()
            current, lines = (m.group(1), m.group(2).strip()), []
        elif current:
            lines.append(line)
    flush()
    return chunks


@lru_cache(maxsize=1)
def load_chunks(policies_dir: str | None = None) -> tuple[Chunk, ...]:
    folder = Path(policies_dir) if policies_dir else get_settings().policies_dir
    out: list[Chunk] = []
    for p in sorted(folder.glob("*.md")):
        out += parse_document(p)
    return tuple(out)


# ---------------------------------------------------------------- retrievers

_STOP = set(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "at",
        "by",
        "with",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "do",
        "does",
        "did",
        "i",
        "my",
        "me",
        "we",
        "our",
        "you",
        "your",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "can",
        "could",
        "should",
        "would",
        "will",
        "what",
        "which",
        "who",
        "how",
        "when",
        "where",
        "why",
        "if",
        "as",
        "any",
        "there",
        "have",
        "has",
        "had",
        "not",
        "no",
        "yes",
        "am",
    ]
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, crude suffix stemming (IR lecture: normalisation)."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for t in tokens:
        if t in _STOP:
            continue
        for suf in ("ing", "ies", "es", "s", "ed"):
            if len(t) > 4 and t.endswith(suf):
                t = t[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        out.append(t)
    return out


class BM25Retriever:
    name = "bm25"

    def __init__(self, chunks: tuple[Chunk, ...]):
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(c.text) for c in chunks])

    def search(self, query: str, k: int = 20) -> list[tuple[Chunk, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in order]


@lru_cache(maxsize=2)
def _sentence_model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu")


class DenseRetriever:
    name = "dense"

    def __init__(self, chunks: tuple[Chunk, ...], model_name: str = DENSE_MODEL):
        self.chunks = chunks
        self.model = _sentence_model(model_name)
        self.emb = self.model.encode([c.text for c in chunks], normalize_embeddings=True, batch_size=32)

    def search(self, query: str, k: int = 20) -> list[tuple[Chunk, float]]:
        q = self.model.encode([DENSE_QUERY_PREFIX + query], normalize_embeddings=True)[0]
        scores = self.emb @ q
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in order]


class HybridRetriever:
    """Reciprocal Rank Fusion of BM25 and dense rankings: score = sum 1 / (k + rank)."""

    name = "hybrid"

    def __init__(self, bm25: BM25Retriever, dense: DenseRetriever, k_rrf: int = RRF_K):
        self.bm25, self.dense, self.k_rrf = bm25, dense, k_rrf

    def search(self, query: str, k: int = 20) -> list[tuple[Chunk, float]]:
        fused: dict[str, float] = {}
        by_id: dict[str, Chunk] = {}
        for retriever in (self.bm25, self.dense):
            for rank, (chunk, _) in enumerate(retriever.search(query, k=50), start=1):
                fused[chunk.id] = fused.get(chunk.id, 0.0) + 1.0 / (self.k_rrf + rank)
                by_id[chunk.id] = chunk
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [(by_id[cid], score) for cid, score in top]


@lru_cache(maxsize=1)
def _cross_encoder(name: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(name, device="cpu")


class Reranker:
    """Cross-encoder reranking of the candidate set. It cannot recover a chunk missing from the candidates."""

    def __init__(self, model_name: str = RERANK_MODEL):
        self.model = _cross_encoder(model_name)

    def rerank(
        self, query: str, candidates: list[tuple[Chunk, float]], k: int = 5
    ) -> list[tuple[Chunk, float]]:
        if not candidates:
            return []
        scores = self.model.predict([(query, c.text) for c, _ in candidates])
        order = np.argsort(-np.asarray(scores))[:k]
        return [(candidates[i][0], float(scores[i])) for i in order]


@dataclass
class RetrievalStack:
    bm25: BM25Retriever
    dense: DenseRetriever
    hybrid: HybridRetriever
    reranker: Reranker

    def retrieve(
        self, query: str, k_candidates: int = 20, k_final: int = 5, rerank: bool = True
    ) -> list[tuple[Chunk, float]]:
        candidates = self.hybrid.search(query, k=k_candidates)
        return self.reranker.rerank(query, candidates, k=k_final) if rerank else candidates[:k_final]


@lru_cache(maxsize=1)
def get_stack() -> RetrievalStack:
    chunks = load_chunks()
    bm25 = BM25Retriever(chunks)
    dense = DenseRetriever(chunks)
    return RetrievalStack(bm25, dense, HybridRetriever(bm25, dense), Reranker())
