from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.lib.fixtures import knowledge_graph


def _adjacency() -> dict[str, list[tuple[str, str]]]:
    graph = knowledge_graph()
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph["edges"]:
        adj[edge["source"]].append((edge["target"], edge["type"]))
        # undirected traversal for exploratory GraphRAG-style walks
        adj[edge["target"]].append((edge["source"], f"INV:{edge['type']}"))
    return adj


def get_entity(entity_id: str) -> dict[str, Any]:
    """Fetch a knowledge-graph node and its immediate edges."""
    entity_id = entity_id.strip().upper()
    graph = knowledge_graph()
    node = next((n for n in graph["nodes"] if n["id"] == entity_id), None)
    if not node:
        result = {"status": "not_found", "entity_id": entity_id, "needs_review": True}
        evidence = record_evidence(
            agent="reconciliation_agent",
            action="get_entity",
            inputs={"entity_id": entity_id},
            outputs=result,
            sources=[],
        )
        result["evidence"] = evidence
        return result

    edges = [
        e
        for e in graph["edges"]
        if e["source"] == entity_id or e["target"] == entity_id
    ]
    result = {
        "status": "success",
        "entity": node,
        "edges": edges,
        "needs_review": False,
    }
    evidence = record_evidence(
        agent="reconciliation_agent",
        action="get_entity",
        inputs={"entity_id": entity_id},
        outputs={"edge_count": len(edges)},
        sources=["fixture:knowledge_graph.json"],
    )
    result["evidence"] = evidence
    return result


def graph_neighborhood(entity_id: str, max_hops: int = 2) -> dict[str, Any]:
    """Multi-hop neighborhood walk for GraphRAG-style reasoning."""
    entity_id = entity_id.strip().upper()
    max_hops = max(1, min(int(max_hops), 4))
    graph = knowledge_graph()
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    if entity_id not in nodes_by_id:
        result = {"status": "not_found", "entity_id": entity_id, "needs_review": True}
        evidence = record_evidence(
            agent="reconciliation_agent",
            action="graph_neighborhood",
            inputs={"entity_id": entity_id, "max_hops": max_hops},
            outputs=result,
            sources=[],
        )
        result["evidence"] = evidence
        return result

    adj = _adjacency()
    visited = {entity_id: 0}
    paths: list[dict[str, Any]] = []
    queue: deque[tuple[str, int, list[str]]] = deque([(entity_id, 0, [entity_id])])

    while queue:
        current, depth, path = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor, rel in adj.get(current, []):
            if neighbor in visited and visited[neighbor] < depth + 1:
                continue
            visited[neighbor] = depth + 1
            new_path = path + [f"-{rel}->", neighbor]
            paths.append(
                {
                    "node": nodes_by_id.get(neighbor, {"id": neighbor}),
                    "depth": depth + 1,
                    "path": new_path,
                }
            )
            queue.append((neighbor, depth + 1, path + [neighbor]))

    result = {
        "status": "success",
        "entity_id": entity_id,
        "max_hops": max_hops,
        "nodes_reached": len(visited),
        "neighborhood": paths[:40],
        "needs_review": False,
    }
    evidence = record_evidence(
        agent="reconciliation_agent",
        action="graph_neighborhood",
        inputs={"entity_id": entity_id, "max_hops": max_hops},
        outputs={"nodes_reached": len(visited)},
        sources=["fixture:knowledge_graph.json"],
    )
    result["evidence"] = evidence
    return result
