# pydrizzle-orm [WIP]

**Python migrations powered by Drizzle** — define your database schema in Python, generate and apply migrations using [drizzle-kit](https://orm.drizzle.team/kit-docs/overview) under the hood.

[![CI](https://github.com/ndamulelonemakh/pydrizzle-orm/actions/workflows/ci.yml/badge.svg)](https://github.com/ndamulelonemakh/pydrizzle-orm/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pydrizzle-orm.svg)](https://pypi.org/project/pydrizzle-orm/)

> Migrations-only. Bring your own query layer.

## Why?

- **Drizzle-kit** has the best migration diffing engine — deterministic, readable SQL output
- **Alembic** has confusing revision chains, unreliable auto-detect, and complex setup
- **pydrizzle-orm** bridges the gap: Python schema definition + Drizzle migration engine

## Quick Start

```bash
pip install pydrizzle-orm
pydrizzle-orm init        # scaffold config + starter schema
pydrizzle-orm generate    # emit Drizzle .ts files
pydrizzle-orm migrate     # create versioned migration files
pydrizzle-orm push        # apply migrations to your database
```

See the [quickstart guide](docs/quickstart.md) for the full walkthrough.

## Define Your Schema

```python
# schema.py
from pydrizzle_orm import pg_table, pg_schema, text, timestamp, jsonb, uuid, pg_enum, index

app = pg_schema("app")

users = pg_table("users", schema=app,
    id=uuid("id").primary_key().default_random(),
    email=text("email").not_null().unique(),
    name=text("name"),
    metadata=jsonb("metadata"),
    created_at=timestamp("created_at").default_now().not_null(),
    indexes=[
        index("users_email_idx").on("email"),
    ],
)
```

> Both `from pydrizzle_orm import ...` and `from pydrizzle_orm.pg import ...` work.
> The shorter form is recommended for new projects.

## Three Schema Input Modes

| Mode | Config `schema_type` | Description |
|------|---------------------|-------------|
| **Native DSL** | `pydrizzle` | Define schemas with pydrizzle-orm's Python API |
| **SQLAlchemy** | `sqlalchemy` | Introspect existing SQLAlchemy models |
| **TypeScript** | `typescript` | Use Drizzle `.ts` schemas directly |

Current implementation status:

- `pydrizzle`: available
- `sqlalchemy`: available
- `typescript`: available

## Requirements

- Python 3.11+
- Node.js or Bun (used to invoke `drizzle-kit`)
- PostgreSQL (MySQL/SQLite planned)

## CLI

```bash
pydrizzle-orm init
pydrizzle-orm generate
pydrizzle-orm push
pydrizzle-orm migrate
pydrizzle-orm studio
pydrizzle-orm status
```

Structured logging controls:

```bash
pydrizzle-orm --log-level DEBUG generate
pydrizzle-orm --log-format json status
```

Environment-based logging controls:

```bash
export PYDRIZZLE_ORM_LOG_LEVEL=DEBUG
export PYDRIZZLE_ORM_LOG_FORMAT=json
```

Library consumers can also configure logging directly:

```python
from pydrizzle_orm import configure_logging

configure_logging(level="INFO", fmt="json")
```

## Development

```bash
make install
make all
make build
```

## CI and Publishing

- GitHub Actions CI runs formatting, linting, unit tests, Testcontainers-backed end-to-end schema push tests, and package build checks
- Publishing uses PyPI trusted publishing with GitHub OIDC, not API tokens
- Manual TestPyPI publish and release-driven PyPI publish are both configured

Release details are in [docs/releasing.md](docs/releasing.md).

## Docs

- [docs/quickstart.md](docs/quickstart.md)
- [docs/releasing.md](docs/releasing.md)


## How it works

                    ┌─────────────────────┐
                    │   pydrizzle.toml    │
                    │ shared defaults     │
                    │ [modes.*] = ...     │
                    └─────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     Mode A: Native    Mode B: SQLAlchemy  Mode C: TypeScript
     pg_table(...)     Base.metadata       schema.ts
              │               │               │
              ▼               ▼               │
         ┌────────────────────────┐           │
         │   Schema IR (shared)   │           │
         │  TableDef, ColumnDef   │           │
         └───────────┬────────────┘           │
                     ▼                        │
              ┌──────────────┐                │
              │  Codegen:    │                │
              │  IR → .ts    │                │
              └──────┬───────┘                │
                     ▼                        ▼
              ┌──────────────────────────────────┐
              │    drizzle-kit generate/push      │
              │    (via bunx/npx under the hood)  │
              └──────────────────────────────────┘

## Status

Alpha. API may change. PostgreSQL support only.


## Roadmap

- [ ] **MySQL and SQLite dialects** — extend beyond PostgreSQL.

- [ ] **Rollback generation** — produce a down-migration alongside each up-migration for safer deployments.

- [ ] **Pre-commit hook** — run `generate` and `migrate` automatically on commit so migration drift never reaches the remote branch.

- [ ] **`pydrizzle-orm[ai]`** — optional extra that uses Claude to translate SQLAlchemy models (or raw DDL) into Drizzle-compatible schema files, reducing manual conversion work.


## License

MIT
