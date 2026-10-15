# API contracts

`openapi.json` is **generated** from the FastAPI app. Do not edit it by hand.

```bash
./scripts/export_openapi.sh          # regenerate
./scripts/export_openapi.sh --check  # CI: fail if stale (also enforced by services/api/tests/test_contract.py)
```

Human-readable conventions, error codes and flows: [`docs/api-contracts.md`](../../docs/api-contracts.md).
