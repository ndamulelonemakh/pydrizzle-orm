# pydrizzle-orm

**Python migrations powered by Drizzle** — define your database schema in Python, generate and apply migrations using [drizzle-kit](https://orm.drizzle.team/kit-docs/overview) under the hood.

[![CI](https://github.com/ndamulelonemakh/pydrizzle-orm/actions/workflows/ci.yml/badge.svg)](https://github.com/ndamulelonemakh/pydrizzle-orm/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pydrizzle-orm.svg)](https://pypi.org/project/pydrizzle-orm/)

> Migrations-only. Bring your own query layer.

## Why?

- **Drizzle-kit** has the best migration diffing engine — deterministic, readable SQL output
- **Alembic** has confusing revision chains, unreliable auto-detect, and complex setup
- **pydrizzle-orm** bridges the gap: Python schema definition + Drizzle migration engine

## Quick Start

Requirements:

- Python 3.11+
- Bun or Node.js on `PATH`
- PostgreSQL database URL exposed as `DATABASE_URL`

```bash
uv pip install pydrizzle-orm
pydrizzle-orm init
pydrizzle-orm generate
pydrizzle-orm push
```

For SQLAlchemy model introspection, install the extra:

```bash
uv pip install 'pydrizzle-orm[sqlalchemy]'
```

If you want one config file to describe multiple schema sources, put them under `[pydrizzle.modes.*]`. `pydrizzle-orm generate` will process every configured entry, and `--mode <name>` can be used to target one entry.

For a fuller setup walkthrough, see [docs/quickstart.md](docs/quickstart.md).

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

## Roadmap

- Evaluate replacing the hand-rolled TOML config layer with `pydantic-settings` if the config surface keeps growing.
- Explore an AI-assisted generation path that uses a coding model such as GPT Codex instead of relying only on manual schema generation flows.

Single-config entry registry:

```toml
[pydrizzle]
dialect = "postgresql"
database_url_env = "DATABASE_URL"
out_dir = ".pydrizzle"

[pydrizzle.modes.native]
schema = "myapp.schemas"
schema_type = "pydrizzle"

[pydrizzle.modes.sqlalchemy]
schema = "myapp.models"
schema_type = "sqlalchemy"

[pydrizzle.modes.typescript]
schema = "src/db/schema"
schema_type = "typescript"
```

Then run:

```bash
pydrizzle generate
pydrizzle --mode sqlalchemy generate
```

For `sqlalchemy` targets, `schema` can be a Python file path, a dotted module name, or a package path. Package targets are walked recursively so split model layouts such as `myapp.models` work without re-exporting every model in one file.

For `pydrizzle` targets, `schema` can also be a Python file path, a dotted module name, or a package path. Package targets are walked recursively so split schema layouts such as `myapp.schemas` work the same way.

For `typescript` targets, `schema` can point at a single `.ts` schema file, an `index.ts` barrel that re-exports schema modules, or a directory of `.ts` schema files. Directory targets are walked recursively so split Drizzle layouts can stay distributed across subfolders.

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

## License

MIT
