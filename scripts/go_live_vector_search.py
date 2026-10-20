#!/usr/bin/env python3
"""2) Export embeddings to GCS and create/deploy a Vertex Vector Search index.

Requires: GOOGLE_CLOUD_PROJECT, ADC/SA, google-cloud-aiplatform, warehouse seeded.

Env:
  FINANCE_OPS_REGION (default us-central1)
  FINANCE_OPS_EMBEDDINGS_BUCKET (default {project}-finance-ops-embeddings)
  FINANCE_OPS_VECTOR_DEPLOYED_INDEX_ID (default finance_ops_policies)
  CLOUD_RUN_SERVICE (default finance-ops) — updated with endpoint when deploy succeeds
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("GOOGLE_CLOUD_PROJECT required", file=sys.stderr)
        return 2
    region = os.environ.get("FINANCE_OPS_REGION", "us-central1")
    bucket = os.environ.get(
        "FINANCE_OPS_EMBEDDINGS_BUCKET", f"{project}-finance-ops-embeddings"
    )
    deployed_id = os.environ.get(
        "FINANCE_OPS_VECTOR_DEPLOYED_INDEX_ID", "finance_ops_policies"
    )
    service = os.environ.get("CLOUD_RUN_SERVICE", "finance-ops")

    # Enable API
    subprocess.check_call(
        ["gcloud", "services", "enable", "aiplatform.googleapis.com", f"--project={project}"]
    )
    subprocess.check_call(
        ["gcloud", "storage", "buckets", "create", f"gs://{bucket}", f"--location={region}", f"--project={project}"],
        stderr=subprocess.DEVNULL,
    ) if False else None
    # bucket may already exist from terraform / prior runs
    subprocess.run(
        ["gcloud", "storage", "buckets", "describe", f"gs://{bucket}", f"--project={project}"],
        check=False,
    )
    if subprocess.run(
        ["gcloud", "storage", "buckets", "describe", f"gs://{bucket}", f"--project={project}"],
        capture_output=True,
    ).returncode != 0:
        subprocess.check_call(
            [
                "gcloud",
                "storage",
                "buckets",
                "create",
                f"gs://{bucket}",
                f"--location={region}",
                f"--project={project}",
            ]
        )

    from data_plane.vectors.embed import build_policy_index
    from pipelines.batch.ingest import ingest_batch

    ingest_batch(run_id="vector-search-go-live")
    built = build_policy_index()
    index_path = Path(built["path"])
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    dim = int(payload.get("dim") or 64)

    # Vertex Vector Search JSONL: {"id": "...", "embedding": [...]}
    local_jsonl = ROOT / ".warehouse" / "vectors" / "me_datapoints.jsonl"
    local_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with local_jsonl.open("w", encoding="utf-8") as fh:
        for item in payload.get("items") or []:
            fh.write(
                json.dumps({"id": item["doc_id"], "embedding": item["embedding"]}) + "\n"
            )

    gcs_prefix = f"gs://{bucket}/vector-search/{int(time.time())}"
    subprocess.check_call(
        ["gcloud", "storage", "cp", str(local_jsonl), f"{gcs_prefix}/me_datapoints.jsonl"]
    )

    try:
        from google.cloud import aiplatform
        from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
    except ImportError:
        print("Install google-cloud-aiplatform", file=sys.stderr)
        return 1

    aiplatform.init(project=project, location=region)

    print("Creating MatchingEngineIndex (this can take 30–90+ minutes)...")
    index = MatchingEngineIndex.create_tree_ah_index(
        display_name="finance-ops-policies",
        contents_delta_uri=gcs_prefix,
        dimensions=dim,
        approximate_neighbors_count=10,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        leaf_node_embedding_count=500,
        leaf_nodes_to_search_percent=10,
        description="Finance ops policy RAG index",
        index_update_method="BATCH_UPDATE",
    )
    print("Index:", index.resource_name)

    print("Creating index endpoint...")
    endpoint = MatchingEngineIndexEndpoint.create(
        display_name="finance-ops-policies-endpoint",
        public_endpoint_enabled=True,
        description="Finance ops policy Vector Search endpoint",
    )
    print("Endpoint:", endpoint.resource_name)

    print(f"Deploying index as {deployed_id}...")
    endpoint = endpoint.deploy_index(
        index=index,
        deployed_index_id=deployed_id,
        display_name=deployed_id,
        min_replica_count=1,
        max_replica_count=1,
    )
    print("Deployed.")

    # Update Cloud Run
    subprocess.check_call(
        [
            "gcloud",
            "run",
            "services",
            "update",
            service,
            f"--region={region}",
            f"--project={project}",
            f"--update-env-vars=FINANCE_OPS_USE_VERTEX_VECTORS=true,FINANCE_OPS_VECTOR_INDEX_ENDPOINT={endpoint.resource_name},FINANCE_OPS_VECTOR_DEPLOYED_INDEX_ID={deployed_id},GOOGLE_CLOUD_PROJECT={project}",
            "--quiet",
        ]
    )

    out = {
        "index": index.resource_name,
        "endpoint": endpoint.resource_name,
        "deployed_index_id": deployed_id,
        "gcs_prefix": gcs_prefix,
        "dim": dim,
        "backend": built.get("backend"),
    }
    out_path = ROOT / ".warehouse" / "vector_search_live.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
