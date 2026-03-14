# Quickstart

Get a Python project using pydrizzle-orm migrations in under 5 minutes.

## Prerequisites

- Python 3.11+
- [Bun](https://bun.sh) or [Node.js](https://nodejs.org) on your `PATH`
- A running PostgreSQL instance

## 1. Install

```bash
pip install pydrizzle-orm
```

## 2. Scaffold

```bash
pydrizzle-orm init
```

This creates a `pydrizzle.toml` config and a starter `schema.py`.

## 3. Define your schema

Edit `schema.py`:

```python
from pydrizzle_orm import pg_table, text, timestamp, uuid, index

users = pg_table(
    "users",
    id=uuid().primary_key().default_random(),
    email=text().not_null().unique(),
    name=text().not_null(),
    created_at=timestamp().default_now().not_null(),
    indexes=[index("users_email_idx").on("email")],
)
```

## 4. Generate Drizzle files

```bash
pydrizzle-orm generate
```

This writes `.pydrizzle/schema.ts` and `.pydrizzle/drizzle.config.ts`.

## 5. Create migration files

```bash
pydrizzle-orm migrate
```

This generates versioned SQL migration files you can review, commit, and apply consistently across environments.

## 6. Apply migrations

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
pydrizzle-orm push
```

That's it — your table is live.

> **Warning:** `pydrizzle-orm push` applies the schema directly without migration files.
> This is convenient for local development and prototyping, but **always use
> `pydrizzle-orm migrate` to generate versioned migration files** for staging and
> production. Versioned migrations are the whole point — they give you a reviewable,
> repeatable, rollback-friendly history of every schema change.

## 7. Check everything is wired up

```bash
pydrizzle-orm status
```

---

## Going further

### SQLAlchemy model introspection

If you already have SQLAlchemy models and want pydrizzle-orm to read them directly, install the extra:

```bash
pip install 'pydrizzle-orm[sqlalchemy]'
```

Then point your config at the models module:

```toml
[pydrizzle]
schema = "myapp.models"
schema_type = "sqlalchemy"
```

### Multiple schema sources

A single config can describe several schema inputs. Add named entries under `[pydrizzle.modes.*]`:

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

`pydrizzle-orm generate` processes every entry. Use `--mode <name>` to target a single one.

For any mode, `schema` can be a file path, a dotted Python module, or a directory — directories are walked recursively.

### JSON logging

```bash
pydrizzle-orm --log-format json status
```
