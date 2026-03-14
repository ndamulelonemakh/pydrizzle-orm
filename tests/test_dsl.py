"""Tests for the native Python DSL — column types, table definitions, enums, indexes, FKs."""

from __future__ import annotations

import pytest

from pydrizzle_orm.ir import SchemaRef
from pydrizzle_orm.pg import (
    EnumType,
    TableProxy,
    boolean,
    index,
    integer,
    json_,
    jsonb,
    pg_enum,
    pg_schema,
    pg_table,
    real,
    serial,
    text,
    timestamp,
    unique_index,
    uuid,
    varchar,
)
from pydrizzle_orm.types import ColumnRef, sql


class TestColumnTypes:
    def test_text_default_name(self) -> None:
        col = text().to_column_def("email")
        assert col.name == "email"
        assert col.python_name == "email"
        assert col.col_type == "text"

    def test_text_explicit_db_name(self) -> None:
        col = text("createdAt").to_column_def("created_at")
        assert col.name == "createdAt"
        assert col.python_name == "created_at"

    def test_uuid_type(self) -> None:
        col = uuid().to_column_def("id")
        assert col.col_type == "uuid"

    def test_integer_type(self) -> None:
        col = integer().to_column_def("count")
        assert col.col_type == "integer"

    def test_real_type(self) -> None:
        col = real("value").to_column_def("value")
        assert col.col_type == "real"

    def test_boolean_type(self) -> None:
        col = boolean().to_column_def("active")
        assert col.col_type == "boolean"

    def test_timestamp_type(self) -> None:
        col = timestamp().to_column_def("created_at")
        assert col.col_type == "timestamp"

    def test_json_type(self) -> None:
        col = json_().to_column_def("data")
        assert col.col_type == "json"

    def test_jsonb_type(self) -> None:
        col = jsonb().to_column_def("metadata")
        assert col.col_type == "jsonb"

    def test_varchar_type(self) -> None:
        col = varchar(length=255).to_column_def("name")
        assert col.col_type == "varchar"
        assert col.varchar_length == 255

    def test_varchar_no_length(self) -> None:
        col = varchar().to_column_def("name")
        assert col.varchar_length is None

    def test_serial_type(self) -> None:
        col = serial().to_column_def("id")
        assert col.col_type == "serial"


class TestColumnConstraints:
    def test_not_null(self) -> None:
        col = text().not_null().to_column_def("name")
        assert col.nullable is False

    def test_default_nullable(self) -> None:
        col = text().to_column_def("name")
        assert col.nullable is True

    def test_primary_key(self) -> None:
        col = uuid().primary_key().to_column_def("id")
        assert col.primary_key is True

    def test_unique(self) -> None:
        col = text().unique().to_column_def("email")
        assert col.unique is True

    def test_array(self) -> None:
        col = text().array().to_column_def("tags")
        assert col.is_array is True

    def test_default_literal_string(self) -> None:
        col = text().default("json").to_column_def("show_input")
        assert col.default == "json"
        assert col.default_is_sql is False

    def test_default_literal_bool(self) -> None:
        col = boolean().default(False).to_column_def("is_error")
        assert col.default is False
        assert col.default_is_sql is False

    def test_default_literal_int(self) -> None:
        col = integer().default(0).to_column_def("count")
        assert col.default == 0
        assert col.default_is_sql is False

    def test_default_sql_expression(self) -> None:
        col = text().default(sql("gen_random_uuid()")).to_column_def("id")
        assert col.default == "gen_random_uuid()"
        assert col.default_is_sql is True

    def test_default_random(self) -> None:
        col = uuid().default_random().to_column_def("id")
        assert col.default == "gen_random_uuid()"
        assert col.default_is_sql is True

    def test_default_now(self) -> None:
        col = timestamp().default_now().to_column_def("created_at")
        assert col.default == "now()"
        assert col.default_is_sql is True

    def test_chaining_multiple(self) -> None:
        col = text("id").primary_key().default(sql("gen_random_uuid()")).to_column_def("id")
        assert col.primary_key is True
        assert col.default == "gen_random_uuid()"
        assert col.default_is_sql is True
        assert col.name == "id"


class TestEnums:
    def test_pg_enum_creates_enum_type(self) -> None:
        e = pg_enum("status", ["active", "inactive"])
        assert isinstance(e, EnumType)
        assert e.name == "status"
        assert e.values == ("active", "inactive")
        assert e.schema is None

    def test_pg_enum_with_schema(self) -> None:
        s = pg_schema("app")
        e = pg_enum("status", ["active"], schema=s)
        assert e.schema == "app"

    def test_enum_to_column_builder(self) -> None:
        e = pg_enum("StepType", ["user_message", "tool"])
        col = e("type").not_null().to_column_def("step_type")
        assert col.col_type == "enum"
        assert col.enum_name == "StepType"
        assert col.name == "type"
        assert col.nullable is False

    def test_enum_to_enum_def(self) -> None:
        e = pg_enum("StepType", ["a", "b"], schema=pg_schema("rhng"))
        ed = e.to_enum_def()
        assert ed.name == "StepType"
        assert ed.values == ("a", "b")
        assert ed.schema == "rhng"


class TestIndexes:
    def test_index_single_column(self) -> None:
        idx = index("users_email_idx").on("email")
        idx_def = idx.to_index_def()
        assert idx_def.name == "users_email_idx"
        assert idx_def.columns == ("email",)
        assert idx_def.unique is False

    def test_index_multiple_columns(self) -> None:
        idx = index("steps_thread_time_idx").on("thread_id", "start_time", "end_time")
        idx_def = idx.to_index_def()
        assert idx_def.columns == ("thread_id", "start_time", "end_time")

    def test_unique_index(self) -> None:
        idx = unique_index("users_email_key").on("email")
        idx_def = idx.to_index_def()
        assert idx_def.unique is True


# Tables


class TestTables:
    def test_basic_table(self) -> None:
        t = pg_table(
            "users",
            id=uuid().primary_key().default_random(),
            email=text().not_null(),
        )
        assert isinstance(t, TableProxy)
        td = t.table_def
        assert td.name == "users"
        assert td.schema is None
        assert len(td.columns) == 2

    def test_table_with_schema(self) -> None:
        s = pg_schema("app")
        t = pg_table("users", schema=s, id=uuid().primary_key())
        assert t.table_def.schema == "app"

    def test_table_with_indexes(self) -> None:
        t = pg_table(
            "users",
            id=uuid().primary_key(),
            email=text().not_null(),
            indexes=[
                index("users_email_idx").on("email"),
                unique_index("users_email_key").on("email"),
            ],
        )
        td = t.table_def
        assert len(td.indexes) == 2
        assert td.indexes[0].name == "users_email_idx"
        assert td.indexes[0].unique is False
        assert td.indexes[1].unique is True

    def test_table_column_order_preserved(self) -> None:
        t = pg_table(
            "test",
            alpha=text(),
            beta=integer(),
            gamma=boolean(),
        )
        names = [c.python_name for c in t.table_def.columns]
        assert names == ["alpha", "beta", "gamma"]

    def test_table_rejects_non_column_builder(self) -> None:
        with pytest.raises(TypeError, match="Expected ColumnBuilder"):
            pg_table("bad", id="not a column")  # type: ignore[arg-type]


# Foreign keys via TableProxy attribute access


class TestForeignKeys:
    def test_column_ref_from_table(self) -> None:
        users = pg_table("users", id=text("id").primary_key())
        ref = users.id
        assert isinstance(ref, ColumnRef)
        assert ref.table_name == "users"
        assert ref.column_name == "id"

    def test_column_ref_with_schema(self) -> None:
        s = pg_schema("app")
        users = pg_table("users", schema=s, id=uuid("id").primary_key())
        ref = users.id
        assert ref.schema_name == "app"

    def test_invalid_column_raises(self) -> None:
        users = pg_table("users", id=uuid().primary_key())
        with pytest.raises(AttributeError, match="has no column 'nonexistent'"):
            _ = users.nonexistent

    def test_references_lambda(self) -> None:
        users = pg_table("users", id=text("id").primary_key())
        posts = pg_table(
            "posts",
            id=text("id").primary_key(),
            user_id=text("userId").references(lambda: users.id),
        )
        user_id_col = posts.table_def.columns[1]
        assert user_id_col.references is not None
        assert user_id_col.references.ref_table == "users"
        assert user_id_col.references.ref_column == "id"


class TestSchemaRef:
    def test_pg_schema(self) -> None:
        s = pg_schema("rhng")
        assert isinstance(s, SchemaRef)
        assert s.name == "rhng"
