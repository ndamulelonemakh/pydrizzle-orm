from __future__ import annotations

from pathlib import Path

from pydrizzle_orm.codegen import generate_typescript
from pydrizzle_orm.parsers.typescript import parse_typescript_schema


def test_parse_example_typescript_schema() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "example"
        / "schemas"
        / "typescript_schema.ts"
    )

    result = parse_typescript_schema(path)

    assert {table.name for table in result.tables} == {
        "users",
        "posts",
        "comments",
        "tags",
        "post_tags",
    }

    users = next(table for table in result.tables if table.name == "users")
    posts = next(table for table in result.tables if table.name == "posts")
    tags = next(table for table in result.tables if table.name == "tags")

    assert users.schema == "public"
    assert any(index.name == "users_email_key" and index.unique for index in users.indexes)

    created_at = next(column for column in users.columns if column.python_name == "createdAt")
    author_id = next(column for column in posts.columns if column.python_name == "authorId")
    status = next(column for column in posts.columns if column.python_name == "status")
    tag_id = next(column for column in tags.columns if column.python_name == "id")

    assert created_at.default == "now()"
    assert created_at.default_is_sql is True
    assert author_id.references is not None
    assert author_id.references.ref_schema == "public"
    assert author_id.references.ref_table == "users"
    assert author_id.references.ref_column == "id"
    assert status.col_type == "enum"
    assert status.enum_name == "post_status"
    assert status.default == "draft"
    assert status.default_is_sql is False
    assert tag_id.col_type == "serial"

    assert [(enum.name, enum.values) for enum in result.enums] == [
        ("post_status", ("draft", "published", "archived"))
    ]


def test_parse_generated_typescript_schema_round_trips() -> None:
    source = """\
import {
  pgEnum,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

export const roleEnum = pgEnum('role', ['admin', 'user']);

export const users = pgTable('users', {
  id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
  email: text('email').notNull(),
  role: roleEnum('role').default('user').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
}, (table) => ({
  usersEmailKey: unique('users_email_key').on(table.email),
}));
"""
    path = Path("/tmp/pydrizzle_typescript_roundtrip.ts")
    path.write_text(source, encoding="utf-8")
    try:
        result = parse_typescript_schema(path)
    finally:
        path.unlink(missing_ok=True)

    output = generate_typescript(result.tables, result.enums)

    assert "pgEnum('role', ['admin', 'user'])" in output
    assert "uuid('id').primaryKey().default(sql`gen_random_uuid()`)," in output
    assert "roleEnum('role').default('user').notNull()," in output
    assert "unique('users_email_key').on(table.email)" in output


def test_parse_typescript_barrel_schema(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()

    (schema_dir / "status.ts").write_text(
        """\
export const statusEnum = pgEnum('status', ['draft', 'published']);
""",
        encoding="utf-8",
    )
    (schema_dir / "users.ts").write_text(
        """\
export const users = pgTable('users', {
  id: uuid('id').primaryKey(),
  email: text('email').notNull(),
});
""",
        encoding="utf-8",
    )
    (schema_dir / "posts.ts").write_text(
        """\
export const posts = pgTable('posts', {
  id: uuid('id').primaryKey(),
  userId: uuid('user_id').notNull().references(() => users.id),
  status: statusEnum('status').default('draft').notNull(),
});
""",
        encoding="utf-8",
    )
    (schema_dir / "index.ts").write_text(
        """\
export * from './status';
export * from './users';
export * from './posts';
""",
        encoding="utf-8",
    )

    result = parse_typescript_schema(schema_dir / "index.ts")

    assert {table.name for table in result.tables} == {"users", "posts"}
    status = next(
        column
        for table in result.tables
        if table.name == "posts"
        for column in table.columns
        if column.python_name == "status"
    )
    user_id = next(
        column
        for table in result.tables
        if table.name == "posts"
        for column in table.columns
        if column.python_name == "userId"
    )

    assert [(enum.name, enum.values) for enum in result.enums] == [
        ("status", ("draft", "published"))
    ]
    assert status.col_type == "enum"
    assert status.enum_name == "status"
    assert user_id.references is not None
    assert user_id.references.ref_table == "users"
    assert user_id.references.ref_column == "id"


def test_parse_typescript_schema_directory(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    nested_dir = schema_dir / "tables"
    nested_dir.mkdir(parents=True)

    (schema_dir / "status.ts").write_text(
        """\
export const statusEnum = pgEnum('status', ['draft', 'published']);
""",
        encoding="utf-8",
    )
    (nested_dir / "users.ts").write_text(
        """\
export const users = pgTable('users', {
  id: uuid('id').primaryKey(),
  email: text('email').notNull(),
});
""",
        encoding="utf-8",
    )
    (nested_dir / "posts.ts").write_text(
        """\
export const posts = pgTable('posts', {
  id: uuid('id').primaryKey(),
  userId: uuid('user_id').notNull().references(() => users.id),
  status: statusEnum('status').default('draft').notNull(),
});
""",
        encoding="utf-8",
    )

    result = parse_typescript_schema(schema_dir)

    assert {table.name for table in result.tables} == {"users", "posts"}
    assert [(enum.name, enum.values) for enum in result.enums] == [
        ("status", ("draft", "published"))
    ]
