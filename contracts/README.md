# TapOrder Canonical API Contract (CONTRACT-1)

- **Revision:** `CONTRACT-1`
- **Canonical Schema:** [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1.0)
- **Generated TypeScript Types:** [`generated/api-types.ts`](generated/api-types.ts)
- **Validated Fixture Examples:** [`examples/`](examples/)
- **Validation & Generation Script:** [`scripts/validate_and_generate.py`](scripts/validate_and_generate.py)

## Commands

From `backend/`:

```bash
# Validate openapi.yaml, all JSON/SSE examples, kitchen DTO projection rules, and TypeScript drift
uv run python ../contracts/scripts/validate_and_generate.py

# Regenerate examples and TypeScript types from canonical contract
uv run python ../contracts/scripts/validate_and_generate.py --write
```

## Policy

1. `contracts/openapi.yaml` is the single source of truth for all 27 business endpoints (`/api/v1/...`) and 2 health probes (`/api/health/live`, `/api/health/ready`).
2. FastAPI serves the canonical schema at `/openapi.json` and contract tests verify route/method/status/security/schema alignment.
3. Role-specific DTOs (`Guest*`, `Kitchen*`, `Cashier*`) are strictly separated; `Kitchen*` schemas are machine-checked to never expose prices, totals, payments, or guest identity.
