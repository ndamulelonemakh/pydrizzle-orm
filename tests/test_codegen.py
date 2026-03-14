"""Codegen snapshot tests — Python IR → Drizzle TypeScript output."""

from __future__ import annotations

import textwrap

from pydrizzle_orm.codegen import generate_drizzle_config, generate_typescript
from pydrizzle_orm.ir import EnumDef, TableDef
from pydrizzle_orm.pg import (
    boolean,
    index,
    integer,
    json_,
    pg_enum,
    pg_schema,
    pg_table,
    real,
    text,
    timestamp,
    unique_index,
    uuid,
)
from pydrizzle_orm.types import sql


def _build_taskmaster_schema() -> tuple[list[TableDef], list[EnumDef]]:
    """Build the TaskMaster schema using pydrizzle DSL, return IR."""
    rhng = pg_schema("rhng")

    step_type_enum = pg_enum(
        "StepType",
        [
            "assistant_message",
            "embedding",
            "llm",
            "retrieval",
            "rerank",
            "run",
            "system_message",
            "tool",
            "undefined",
            "user_message",
        ],
        schema=rhng,
    )

    users = pg_table(
        "User",
        schema=rhng,
        id=text("id").primary_key().default(sql("gen_random_uuid()")),
        created_at=timestamp("createdAt").default_now().not_null(),
        updated_at=timestamp("updatedAt").default_now().not_null(),
        metadata=json_("metadata").not_null(),
        identifier=text("identifier").not_null(),
        indexes=[
            index("User_identifier_idx").on("identifier"),
            unique_index("User_identifier_key").on("identifier"),
        ],
    )

    threads = pg_table(
        "Thread",
        schema=rhng,
        id=text("id").primary_key().default(sql("gen_random_uuid()")),
        created_at=timestamp("createdAt").default_now().not_null(),
        updated_at=timestamp("updatedAt").default_now().not_null(),
        deleted_at=timestamp("deletedAt"),
        name=text("name"),
        metadata=json_("metadata").not_null(),
        tags=text("tags").array().default(sql("ARRAY[]::text[]")).not_null(),
        user_id=text("userId"),
        indexes=[
            index("Thread_createdAt_idx").on("created_at"),
            index("Thread_name_idx").on("name"),
        ],
    )

    steps = pg_table(
        "Step",
        schema=rhng,
        id=text("id").primary_key().default(sql("gen_random_uuid()")),
        created_at=timestamp("createdAt").default_now().not_null(),
        updated_at=timestamp("updatedAt").default_now().not_null(),
        parent_id=text("parentId"),
        thread_id=text("threadId"),
        input=text("input"),
        metadata=json_("metadata").not_null(),
        name=text("name"),
        output=text("output"),
        type=step_type_enum("type").not_null(),
        show_input=text("showInput").default("json"),
        is_error=boolean("isError").default(False),
        start_time=timestamp("startTime").not_null(),
        end_time=timestamp("endTime").not_null(),
        indexes=[
            index("Step_createdAt_idx").on("created_at"),
            index("Step_endTime_idx").on("end_time"),
            index("Step_parentId_idx").on("parent_id"),
            index("Step_startTime_idx").on("start_time"),
            index("Step_threadId_idx").on("thread_id"),
            index("Step_type_idx").on("type"),
            index("Step_name_idx").on("name"),
            index("Step_threadId_startTime_endTime_idx").on("thread_id", "start_time", "end_time"),
        ],
    )

    elements = pg_table(
        "Element",
        schema=rhng,
        id=text("id").primary_key().default(sql("gen_random_uuid()")),
        created_at=timestamp("createdAt").default_now().not_null(),
        updated_at=timestamp("updatedAt").default_now().not_null(),
        thread_id=text("threadId"),
        step_id=text("stepId").not_null(),
        metadata=json_("metadata").not_null(),
        mime=text("mime"),
        name=text("name").not_null(),
        object_key=text("objectKey"),
        url=text("url"),
        chainlit_key=text("chainlitKey"),
        display=text("display"),
        size=text("size"),
        language=text("language"),
        page=integer("page"),
        props=json_("props"),
        indexes=[
            index("Element_stepId_idx").on("step_id"),
            index("Element_threadId_idx").on("thread_id"),
        ],
    )

    feedback = pg_table(
        "Feedback",
        schema=rhng,
        id=text("id").primary_key().default(sql("gen_random_uuid()")),
        created_at=timestamp("createdAt").default_now().not_null(),
        updated_at=timestamp("updatedAt").default_now().not_null(),
        step_id=text("stepId"),
        name=text("name").not_null(),
        value=real("value").not_null(),
        comment=text("comment"),
        indexes=[
            index("Feedback_createdAt_idx").on("created_at"),
            index("Feedback_name_idx").on("name"),
            index("Feedback_stepId_idx").on("step_id"),
            index("Feedback_value_idx").on("value"),
            index("Feedback_name_value_idx").on("name", "value"),
        ],
    )

    tables = [
        users.table_def,
        threads.table_def,
        steps.table_def,
        elements.table_def,
        feedback.table_def,
    ]
    enums = [step_type_enum.to_enum_def()]
    return tables, enums


class TestCodegenBasic:
    def test_simple_table_no_schema(self) -> None:
        t = pg_table("users", id=uuid("id").primary_key(), name=text("name"))
        output = generate_typescript([t.table_def])
        assert "pgTable" in output
        assert "export const users = pgTable('users'" in output
        assert "id: uuid('id').primaryKey()," in output
        assert "name: text('name')," in output

    def test_table_with_schema(self) -> None:
        s = pg_schema("app")
        t = pg_table("users", schema=s, id=text("id").primary_key())
        output = generate_typescript([t.table_def])
        assert "pgSchema" in output
        assert "export const appSchema = pgSchema('app');" in output
        assert "appSchema.table('users'" in output

    def test_public_schema_uses_pgTable(self) -> None:
        s = pg_schema("public")
        e = pg_enum("status", ["active", "inactive"], schema=s)
        t = pg_table("users", schema=s, id=text("id").primary_key(), status=e("status"))
        output = generate_typescript([t.table_def], [e.to_enum_def()])
        assert "pgSchema" not in output
        assert "pgTable('users'" in output
        assert "pgEnum('status'" in output

    def test_default_now_generates_defaultNow(self) -> None:
        t = pg_table("t", created=timestamp("created").default_now().not_null())
        output = generate_typescript([t.table_def])
        assert ".defaultNow().notNull()" in output

    def test_sql_default(self) -> None:
        t = pg_table("t", id=text("id").default(sql("gen_random_uuid()")))
        output = generate_typescript([t.table_def])
        assert ".default(sql`gen_random_uuid()`)" in output
        assert "import { sql } from 'drizzle-orm';" in output

    def test_literal_string_default(self) -> None:
        t = pg_table("t", mode=text("mode").default("draft"))
        output = generate_typescript([t.table_def])
        assert ".default('draft')" in output

    def test_literal_bool_default(self) -> None:
        t = pg_table("t", active=boolean("active").default(False))
        output = generate_typescript([t.table_def])
        assert ".default(false)" in output

    def test_array_column(self) -> None:
        t = pg_table("t", tags=text("tags").array().not_null())
        output = generate_typescript([t.table_def])
        assert ".array().notNull()" in output

    def test_indexes_in_third_arg(self) -> None:
        t = pg_table(
            "users",
            id=text("id").primary_key(),
            email=text("email"),
            indexes=[index("users_email_idx").on("email")],
        )
        output = generate_typescript([t.table_def])
        assert "(table) => ({" in output
        assert "index('users_email_idx').on(table.email)" in output

    def test_unique_column_generates_constraint(self) -> None:
        t = pg_table("users", email=text("email").unique())
        output = generate_typescript([t.table_def])
        assert "unique('users_email_key').on(table.email)" in output


class TestCodegenEnum:
    def test_enum_in_schema(self) -> None:
        s = pg_schema("app")
        e = pg_enum("status", ["active", "inactive"], schema=s)
        t = pg_table("users", schema=s, status=e("status").not_null())
        output = generate_typescript([t.table_def], [e.to_enum_def()])
        assert "appSchema.enum('status', ['active', 'inactive'])" in output
        assert "statusEnum('status').notNull()" in output

    def test_enum_without_schema(self) -> None:
        e = pg_enum("role", ["admin", "user"])
        t = pg_table("users", role=e("role"))
        output = generate_typescript([t.table_def], [e.to_enum_def()])
        assert "pgEnum('role', ['admin', 'user'])" in output


class TestCodegenForeignKey:
    def test_references_generates_callback(self) -> None:
        users = pg_table("users", id=text("id").primary_key())
        posts = pg_table(
            "posts",
            id=text("id").primary_key(),
            user_id=text("userId").references(lambda: users.id),
        )
        output = generate_typescript([users.table_def, posts.table_def])
        assert ".references(() => users.id)" in output


class TestCodegenTaskmasterSnapshot:
    """Golden-file style snapshot test against the full TaskMaster schema."""

    def test_taskmaster_schema_generates_valid_typescript(self) -> None:
        tables, enums = _build_taskmaster_schema()
        output = generate_typescript(tables, enums)

        # Structural assertions — the generated TS must contain these
        assert "export const rhngSchema = pgSchema('rhng');" in output
        assert "rhngSchema.enum('StepType'" in output
        assert "rhngSchema.table('User'" in output
        assert "rhngSchema.table('Thread'" in output
        assert "rhngSchema.table('Step'" in output
        assert "rhngSchema.table('Element'" in output
        assert "rhngSchema.table('Feedback'" in output

        # Column types
        assert "text('id').primaryKey()" in output
        assert "timestamp('createdAt').defaultNow().notNull()" in output
        assert "json('metadata').notNull()" in output
        assert "text('tags').array().default(sql`ARRAY[]::text[]`).notNull()" in output
        assert "boolean('isError').default(false)" in output
        assert "text('showInput').default('json')" in output
        assert "real('value').notNull()" in output
        assert "integer('page')" in output

        # Indexes
        assert "index('User_identifier_idx')" in output
        assert "unique('User_identifier_key')" in output
        assert "index('Step_threadId_startTime_endTime_idx')" in output

        # Imports
        assert "from 'drizzle-orm/pg-core'" in output
        assert "import { sql } from 'drizzle-orm';" in output

    def test_taskmaster_full_snapshot(self) -> None:
        """Full text snapshot — update this when codegen changes intentionally."""
        tables, enums = _build_taskmaster_schema()
        output = generate_typescript(tables, enums)

        expected = textwrap.dedent("""\
            import {
              boolean,
              index,
              integer,
              json,
              pgSchema,
              real,
              text,
              timestamp,
              unique,
            } from 'drizzle-orm/pg-core';
            import { sql } from 'drizzle-orm';

            export const rhngSchema = pgSchema('rhng');

            export const stepTypeEnum = rhngSchema.enum('StepType', ['assistant_message', 'embedding', 'llm', 'retrieval', 'rerank', 'run', 'system_message', 'tool', 'undefined', 'user_message']);

            export const user = rhngSchema.table('User', {
              id: text('id').primaryKey().default(sql`gen_random_uuid()`),
              createdAt: timestamp('createdAt').defaultNow().notNull(),
              updatedAt: timestamp('updatedAt').defaultNow().notNull(),
              metadata: json('metadata').notNull(),
              identifier: text('identifier').notNull(),
            }, (table) => ({
              userIdentifierIdx: index('User_identifier_idx').on(table.identifier),
              userIdentifierKey: unique('User_identifier_key').on(table.identifier),
            }));

            export const thread = rhngSchema.table('Thread', {
              id: text('id').primaryKey().default(sql`gen_random_uuid()`),
              createdAt: timestamp('createdAt').defaultNow().notNull(),
              updatedAt: timestamp('updatedAt').defaultNow().notNull(),
              deletedAt: timestamp('deletedAt'),
              name: text('name'),
              metadata: json('metadata').notNull(),
              tags: text('tags').array().default(sql`ARRAY[]::text[]`).notNull(),
              userId: text('userId'),
            }, (table) => ({
              threadCreatedAtIdx: index('Thread_createdAt_idx').on(table.createdAt),
              threadNameIdx: index('Thread_name_idx').on(table.name),
            }));

            export const step = rhngSchema.table('Step', {
              id: text('id').primaryKey().default(sql`gen_random_uuid()`),
              createdAt: timestamp('createdAt').defaultNow().notNull(),
              updatedAt: timestamp('updatedAt').defaultNow().notNull(),
              parentId: text('parentId'),
              threadId: text('threadId'),
              input: text('input'),
              metadata: json('metadata').notNull(),
              name: text('name'),
              output: text('output'),
              type: stepTypeEnum('type').notNull(),
              showInput: text('showInput').default('json'),
              isError: boolean('isError').default(false),
              startTime: timestamp('startTime').notNull(),
              endTime: timestamp('endTime').notNull(),
            }, (table) => ({
              stepCreatedAtIdx: index('Step_createdAt_idx').on(table.createdAt),
              stepEndTimeIdx: index('Step_endTime_idx').on(table.endTime),
              stepParentIdIdx: index('Step_parentId_idx').on(table.parentId),
              stepStartTimeIdx: index('Step_startTime_idx').on(table.startTime),
              stepThreadIdIdx: index('Step_threadId_idx').on(table.threadId),
              stepTypeIdx: index('Step_type_idx').on(table.type),
              stepNameIdx: index('Step_name_idx').on(table.name),
              stepThreadIdStartTimeEndTimeIdx: index('Step_threadId_startTime_endTime_idx').on(table.threadId, table.startTime, table.endTime),
            }));

            export const element = rhngSchema.table('Element', {
              id: text('id').primaryKey().default(sql`gen_random_uuid()`),
              createdAt: timestamp('createdAt').defaultNow().notNull(),
              updatedAt: timestamp('updatedAt').defaultNow().notNull(),
              threadId: text('threadId'),
              stepId: text('stepId').notNull(),
              metadata: json('metadata').notNull(),
              mime: text('mime'),
              name: text('name').notNull(),
              objectKey: text('objectKey'),
              url: text('url'),
              chainlitKey: text('chainlitKey'),
              display: text('display'),
              size: text('size'),
              language: text('language'),
              page: integer('page'),
              props: json('props'),
            }, (table) => ({
              elementStepIdIdx: index('Element_stepId_idx').on(table.stepId),
              elementThreadIdIdx: index('Element_threadId_idx').on(table.threadId),
            }));

            export const feedback = rhngSchema.table('Feedback', {
              id: text('id').primaryKey().default(sql`gen_random_uuid()`),
              createdAt: timestamp('createdAt').defaultNow().notNull(),
              updatedAt: timestamp('updatedAt').defaultNow().notNull(),
              stepId: text('stepId'),
              name: text('name').notNull(),
              value: real('value').notNull(),
              comment: text('comment'),
            }, (table) => ({
              feedbackCreatedAtIdx: index('Feedback_createdAt_idx').on(table.createdAt),
              feedbackNameIdx: index('Feedback_name_idx').on(table.name),
              feedbackStepIdIdx: index('Feedback_stepId_idx').on(table.stepId),
              feedbackValueIdx: index('Feedback_value_idx').on(table.value),
              feedbackNameValueIdx: index('Feedback_name_value_idx').on(table.name, table.value),
            }));
        """)

        assert output == expected


class TestCodegenConfig:
    def test_basic_config(self) -> None:
        output = generate_drizzle_config(
            schema_path="./schema.ts",
            out_dir="./migrations",
            database_url_env="DB_URL",
            schema_filter=["app"],
        )
        assert 'dialect: "postgresql"' in output
        assert 'schema: "./schema.ts"' in output
        assert "process.env.DB_URL!" in output
        assert "schemaFilter: ['app']" in output

    def test_no_schema_filter(self) -> None:
        output = generate_drizzle_config()
        assert "schemaFilter" not in output
