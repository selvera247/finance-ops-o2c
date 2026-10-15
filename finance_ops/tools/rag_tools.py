from __future__ import annotations

import re
from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.lib.fixtures import rag_corpus


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def search_policies(query: str, top_k: int = 3) -> dict[str, Any]:
    """Keyword RAG over local finance policy corpus (Vector Search stand-in)."""
    top_k = max(1, min(int(top_k), 5))
    q_tokens = _tokenize(query)
    scored: list[dict[str, Any]] = []
    for doc in rag_corpus():
        doc_tokens = _tokenize(doc["title"] + " " + doc["text"])
        overlap = q_tokens & doc_tokens
        if not overlap:
            continue
        score = len(overlap) / max(len(q_tokens), 1)
        scored.append(
            {
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "snippet": doc["text"][:280],
                "score": round(score, 3),
                "matched_terms": sorted(overlap),
            }
        )
    scored.sort(key=lambda d: d["score"], reverse=True)
    hits = scored[:top_k]
    result = {
        "status": "success",
        "query": query,
        "hits": hits,
        "needs_review": len(hits) == 0,
    }
    evidence = record_evidence(
        agent="coordinator",
        action="search_policies",
        inputs={"query": query, "top_k": top_k},
        outputs={"hit_ids": [h["doc_id"] for h in hits]},
        sources=[f"fixture:rag_corpus.json:{h['doc_id']}" for h in hits],
    )
    result["evidence"] = evidence
    return result
