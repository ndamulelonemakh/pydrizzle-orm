# pydrizzle-orm example — blog platform

A FastAPI demo that shows all three pydrizzle-orm operating modes against a blog schema:
`users → posts → comments`, with `tags` and a `post_tags` junction table.

## Setup

```bash
cd docs/example
uv pip install -e .
```

## Run

```bash
uv run uvicorn app:app --reload
```

Open http://localhost:8000 — the interactive demo loads in your browser.

### In-app database flow

Once the app is running:

1. Click `Test connection` to verify `DATABASE_URL` can be reached.
2. Click `Generate` for the selected mode.
3. Click `Push` to run `drizzle-kit push` for that target.
4. Check the `public tables` list in the UI to confirm tables were created.

## Local database

The example works better with a disposable Postgres instance you can reset without touching a real environment. A ready-to-run Compose file is included at [compose.yaml](compose.yaml).

```bash
docker compose -f compose.yaml up -d
export DATABASE_URL=postgresql://postgres:postgres@localhost:5434/pydrizzle_example
```

Wait for the container healthcheck to pass, then run the CLI against that database.

To tear it down:

```bash
docker compose -f compose.yaml down -v
```

## CLI usage

```bash
# generate every configured target from the shared manifest
pydrizzle-orm generate

# inspect one configured target
pydrizzle-orm --mode native status

# push the supported native target via drizzle-kit (requires Node + drizzle-kit installed)
pydrizzle-orm --mode native push

# launch Drizzle Studio against the local Postgres container
pydrizzle-orm --mode native studio

# check the full manifest status
pydrizzle-orm status
```

The example config already uses `database_url_env = "DATABASE_URL"`, so the exported value is picked up automatically.

All three targets live in one config file: [pydrizzle.toml](pydrizzle.toml).

The base `[pydrizzle]` section holds shared defaults. The target-specific schema pointers live under `[pydrizzle.modes.*]`:

| Mode | Config file | Schema source |
|---|---|---|
| `native` | `pydrizzle.toml` | `schemas/native_schema.py` |
| `sqlalchemy` | `pydrizzle.toml` | `schemas/sqlalchemy_models.py` |
| `typescript` | `pydrizzle.toml` | `schemas/typescript_schema.ts` |

Inside the demo app, the UI reads those targets from the package config loader in [app.py](app.py).

## CI direction

CI now has the same full-circle path: a disposable Postgres container plus a real `pydrizzle-orm push` run. The repository uses Testcontainers so each end-to-end run gets an isolated database and verifies that the generated schema is actually accepted by Postgres.

Locally, you can run the same path with:

```bash
make test-e2e
```

That requires Docker plus Bun or Node on your machine, because the test invokes the real `drizzle-kit` flow.

## Operating modes

| Mode | Schema source | Parser status |
|---|---|---|
| `pydrizzle` | `schemas/native_schema.py` | ✅ supported |
| `sqlalchemy` | `schemas/sqlalchemy_models.py` | ✅ supported |
| `typescript` | `schemas/typescript_schema.ts` | ✅ supported |

## Project layout

```
app.py                   FastAPI application
schemas/
  native_schema.py       pydrizzle DSL (Python)
  sqlalchemy_models.py   SQLAlchemy 2.0 declarative models
  typescript_schema.ts   drizzle-orm TypeScript (hand-written reference)
static/
  index.html             browser demo UI
pydrizzle.toml           shared multi-target CLI config
compose.yaml             disposable PostgreSQL for local testing
pyproject.toml           project dependencies
```
