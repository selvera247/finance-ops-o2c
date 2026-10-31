# Cloud Run — free visibility vs gated writes

**Service:** `finance-ops`  
**URL:** https://finance-ops-301858971164.us-central1.run.app

## Free (no token)

Share these for the free wedge / pilot phase 1:

```bash
BASE=https://finance-ops-301858971164.us-central1.run.app
curl -s "$BASE/health" | jq .auth
curl -s "$BASE/v1/ar_exception_queue" | jq .metrics
curl -s "$BASE/v1/ar/exceptions?status=open&limit=20"
curl -s "$BASE/v1/ar/metrics"
curl -s "$BASE/v1/ar/skus"
curl -s -X POST "$BASE/v1/suggest_payment_match" \
  -H 'content-type: application/json' \
  -d '{"payment_id":"PAY-1001"}'
```

Also free: `POST /v1/aging`, `GET /docs`.

## Paid / ops (token required)

After deploy with `FINANCE_OPS_API_TOKEN` set:

```bash
TOKEN=…   # same value as Cloud Run env
curl -s -X POST "$BASE/v1/request_cash_app_approval" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"payment_id":"PAY-1001"}'
```

Gated routes: sync, triage, `request_cash_app_approval`, `decide_approval`, `request_approval`, `bootstrap`.  
Governance routes still use `FINANCE_OPS_GOVERNANCE_TOKEN`. HubSpot webhook keeps its own signature.

## Set the token on Cloud Run

```bash
# Generate once; store in secret manager in prod
TOKEN=$(openssl rand -hex 24)

gcloud run services update finance-ops \
  --region=us-central1 \
  --update-env-vars="FINANCE_OPS_API_TOKEN=$TOKEN"
```

Redeploy the revision that includes write-auth in `finance_ops/serving.py` (this change), then set the env var if not baked into the new revision’s env.

Without a token on Cloud Run, mutating calls return **503** (`write auth not configured`). Free GETs still work.

## Local / pytest

Writes stay open when `K_SERVICE` is unset and no API token / `FINANCE_OPS_LOCK_WRITES` — so existing tests keep working. Force lock locally with `FINANCE_OPS_LOCK_WRITES=1`.
