# SNEHA API (FastAPI)

See the repository root `README.md` for full setup. Quick reference (run from this directory):

```bash
uv sync                                   # install dependencies into .venv
cp .env.example .env                      # local configuration (git-ignored)
uv run alembic upgrade head               # apply migrations
uv run uvicorn app.main:app --reload      # http://localhost:8000/docs
uv run pytest                             # tests
uv run ruff check . && uv run ruff format --check .
uv run python scripts/export_openapi.py   # regenerate packages/api_contracts/openapi.json
```

Layout:

```
app/
  main.py            application factory (create_app)
  core/              config, errors, request IDs, time and ID helpers
  db/                SQLAlchemy base, sessions, migration helpers, model registry
  api/               routers and dependency aliases (all routes under /api/v1)
  schemas/           Pydantic request/response models (the API contract)
migrations/          Alembic environment and revisions
scripts/             maintenance scripts (OpenAPI export)
tests/               pytest suite
```
