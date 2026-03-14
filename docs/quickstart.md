# Quickstart

## Requirements

- Python 3.11+
- Bun or Node.js available on `PATH`
- PostgreSQL database URL in `DATABASE_URL`

## Install

```bash
uv pip install pydrizzle
```

If you want to read SQLAlchemy models directly:

```bash
uv pip install 'pydrizzle[sqlalchemy]'
```

Or with `pip`:

```bash
pip install pydrizzle
```

## Bootstrap a project

```bash
pydrizzle init
```

This creates:

- `pydrizzle.toml`
- `schema.py`
- `.pydrizzle/` after generation

If you want one config file to describe multiple schema sources, add named entries under `[pydrizzle.modes.*]`:

```toml
[pydrizzle]
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

For `pydrizzle`, `schema` can point at a single file, a dotted module like `myapp.schemas`, or a package directory. Package targets are imported and walked recursively so split schema modules can stay in subpackages.

For `sqlalchemy`, `schema` can point at a single file, a dotted module like `myapp.models`, or a package directory. Package targets are imported and walked recursively so models can stay split across submodules.

For `typescript`, `schema` can point at a single `.ts` schema file, an `index.ts` barrel that re-exports schema modules, or a directory of `.ts` schema files. Directory targets are walked recursively so split Drizzle schemas can stay spread across subfolders.

`pydrizzle generate` will walk every configured entry. If multiple entries share the same base `out_dir`, outputs are written into per-entry subdirectories such as `.pydrizzle/native/` and `.pydrizzle/sqlalchemy/`.

Use `--mode native` when you want to target only one named entry.

## Generate Drizzle files

```bash
pydrizzle generate
```

Generated output:

- `.pydrizzle/schema.ts`
- `.pydrizzle/drizzle.config.ts`

With multiple named entries, expect one output folder per entry under the shared base directory unless that entry overrides `out_dir`.

`sqlalchemy` and `typescript` targets are supported for generation the same way as native targets.

## Apply schema directly

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/app
pydrizzle push
```

## Create migration files

```bash
pydrizzle migrate
```

## Inspect setup

```bash
pydrizzle status
pydrizzle --log-format json status
```

## Minimal schema example

```python
from pydrizzle.pg import index, pg_table, text, timestamp, uuid

users = pg_table(
    "users",
    id=uuid().primary_key().default_random(),
    email=text().not_null().unique(),
    name=text().not_null(),
    created_at=timestamp("created_at").default_now().not_null(),
    indexes=[index("users_email_idx").on("email")],
)
```
