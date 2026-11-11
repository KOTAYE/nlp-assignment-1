"""Indexer / chunker evaluation.

1. Section integrity (deterministic): every `### N.M` heading in the corpus maps to exactly one chunk, every chunk
   is non-empty, no table is split across chunks, every chunk carries doc title + parent heading metadata.
2. Chunking ablation (retrieval Recall@5 / MRR with BM25 on the QA questions): section-aware chunks vs fixed-size
   120-word chunks with 30-word overlap (RAG lecture: fixed-size vs structure-aware chunking).
"""

from __future__ import annotations

import re

from evals.common import load, mean_dicts, ranking_metrics, save, split_arg
from hr_assistant.config import get_settings
from hr_assistant.retrieval import BM25Retriever, Chunk, load_chunks


def fixed_size_chunks(chunks: tuple[Chunk, ...], size: int = 120, overlap: int = 30) -> tuple[Chunk, ...]:
    """Concatenate each document and cut into fixed windows; each window keeps the IDs of the sections it covers."""
    out: list[Chunk] = []
    by_doc: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c)
    for doc_id, cs in by_doc.items():
        words: list[tuple[str, str]] = []
        for c in cs:
            words += [(w, c.id) for w in (c.heading + " " + c.body).split()]
        i = n = 0
        while i < len(words):
            win = words[i : i + size]
            ids = sorted({cid for _, cid in win})
            n += 1
            out.append(
                Chunk("|".join(ids), doc_id, cs[0].doc_title, str(n), "", "", " ".join(w for w, _ in win))
            )
            i += size - overlap
    return tuple(out)


def main() -> None:
    args = split_arg("all")
    chunks = load_chunks()
    corpus_sections = []
    for p in sorted(get_settings().policies_dir.glob("*.md")):
        doc = re.search(r"^doc_id: (.+)$", p.read_text(encoding="utf-8"), re.M).group(1).strip()
        corpus_sections += [
            f"{doc} §{m}" for m in re.findall(r"^### (\d+\.\d+) ", p.read_text(encoding="utf-8"), re.M)
        ]
    ids = [c.id for c in chunks]
    tables_ok = all(
        (lines := [ln for ln in c.body.splitlines() if ln.startswith("|")]) == []
        or lines[0].count("|") == lines[-1].count("|")
        for c in chunks
    )
    integrity = {
        "sections_in_corpus": len(corpus_sections),
        "chunks": len(chunks),
        "every_section_one_chunk": sorted(ids) == sorted(corpus_sections) and len(set(ids)) == len(ids),
        "empty_chunks": sum(not c.body.strip() for c in chunks),
        "tables_intact": tables_ok,
        "metadata_present": all(c.doc_title and c.parent and c.heading for c in chunks),
        "avg_words_per_chunk": round(sum(len(c.body.split()) for c in chunks) / len(chunks), 1),
    }

    qa = [r for r in load("qa", args.split) if r["gold_outcome"] == "answer"]
    results = {}
    per_row = []
    for name, cs in (("section_aware", chunks), ("fixed_120w", fixed_size_chunks(chunks))):
        bm = BM25Retriever(cs)
        scores = []
        for r in qa:
            gold = set(r["gold_section_ids"])
            ranked = []
            for c, _ in bm.search(r["question"], k=10):  # map multi-section windows back to section IDs
                for sid in c.id.split("|"):
                    if sid not in ranked:
                        ranked.append(sid)
            m = ranking_metrics(ranked, gold)
            scores.append(m)
            per_row.append({"variant": name, "id": r["id"], "hit@5": m["hit@5"], "mrr@10": m["mrr@10"]})
        results[name] = mean_dicts(scores)
    save("indexer", {**integrity, "ablation_bm25": results}, per_row, args.split)


if __name__ == "__main__":
    main()
