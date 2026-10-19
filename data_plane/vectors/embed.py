from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from data_plane.config import VECTOR_DIR, ensure_dirs
from data_plane.warehouse import db

DIM = 64
INDEX_PATH = VECTOR_DIR / "policy_index.json"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def hash_embed(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = hash(tok)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def build_policy_index() -> dict[str, Any]:
    ensure_dirs()
    db.init_schema()
    docs = db.query_dicts("SELECT doc_id, title, text FROM policy_docs")
    items = []
    for doc in docs:
        text = f"{doc['title']}\n{doc['text']}"
        items.append({
            "doc_id": doc["doc_id"], "title": doc["title"], "text": doc["text"],
            "embedding": hash_embed(text),
        })
    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "backend": "local_hash", "dim": DIM, "count": len(items), "items": items,
    }
    INDEX_PATH.write_text(json.dumps(payload), encoding="utf-8")
    run_id = f"vectors-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    db.execute(
        "INSERT OR REPLACE INTO pipeline_runs VALUES (?,?,?,?,?,?)",
        [run_id, "vectors", "success", f"count={len(items)}", now, now],
    )
    return {"status": "success", "count": len(items), "path": str(INDEX_PATH), "run_id": run_id}


def search(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    if not INDEX_PATH.exists():
        build_policy_index()
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    q = hash_embed(query)
    scored = []
    for item in index["items"]:
        scored.append({
            "doc_id": item["doc_id"], "title": item["title"],
            "snippet": item["text"][:280], "score": round(cosine(q, item["embedding"]), 4),
        })
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[: max(1, min(top_k, 5))]


def vertex_vector_status() -> dict[str, Any]:
    enabled = os.getenv("FINANCE_OPS_USE_VERTEX_VECTORS", "false").lower() in {"1", "true", "yes"}
    return {"enabled": enabled, "note": "Local hash embeddings active by default."}
