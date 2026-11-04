# Copilot fixtures (email + remittance)

| Path | Purpose |
| --- | --- |
| `actor_acl.json` | Actor → customer_id allowlist (`*` = all). Fail closed for unknown actors. |
| `mailbox/messages.json` | Shared-mailbox style threads for CI (`COPILOT_EMAIL_EVIDENCE=1`) |
| `remittance/REM-PAY-1001.*` | Text-layer PDF + sidecar txt/json with invoice/amount fields |
| `remittance/REM-SCAN-THIN.*` | Low-quality OCR stand-in → thin evidence / abstain |

Override paths via `COPILOT_ACTOR_ACL_PATH`, `COPILOT_MAILBOX_FIXTURE`, `COPILOT_REMITTANCE_DIR`.
