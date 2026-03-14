"""PostgreSQL schema DSL — the native pydrizzle-orm way to define schemas."""

from __future__ import annotations

from typing import Any

from pydrizzle_orm.ir import EnumDef, SchemaRef, TableDef
from pydrizzle_orm.types import ColumnBuilder, ColumnRef, IndexBuilder


def pg_schema(name: str) -> SchemaRef:
    return SchemaRef(name=name)


class EnumType:
    def __init__(self, name: str, values: list[str], schema: SchemaRef | None = None) -> None:
        self.name = name
        self.values = tuple(values)
        self.schema = schema.name if schema else None

    def __call__(self, db_name: str | None = None) -> ColumnBuilder:
        return ColumnBuilder("enum", db_name, enum_name=self.name)

    def to_enum_def(self) -> EnumDef:
        return EnumDef(name=self.name, values=self.values, schema=self.schema)


def pg_enum(name: str, values: list[str], *, schema: SchemaRef | None = None) -> EnumType:
    return EnumType(name, values, schema)


def uuid(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("uuid", db_name)


def text(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("text", db_name)


def integer(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("integer", db_name)


def real(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("real", db_name)


def boolean(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("boolean", db_name)


def timestamp(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("timestamp", db_name)


def json_(db_name: str | None = None) -> ColumnBuilder:
    """JSON column. Named json_ to avoid shadowing the built-in."""
    return ColumnBuilder("json", db_name)


def jsonb(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("jsonb", db_name)


def varchar(db_name: str | None = None, *, length: int | None = None) -> ColumnBuilder:
    builder = ColumnBuilder("varchar", db_name)
    if length is not None:
        builder._varchar_length = length
    return builder


def serial(db_name: str | None = None) -> ColumnBuilder:
    return ColumnBuilder("serial", db_name)


def index(name: str) -> IndexBuilder:
    return IndexBuilder(name)


def unique_index(name: str) -> IndexBuilder:
    return IndexBuilder(name, unique=True)


class TableProxy:
    def __init__(self, table_def: TableDef) -> None:
        self._table_def = table_def
        self._columns = {col.python_name: col for col in table_def.columns}

    @property
    def table_def(self) -> TableDef:
        return self._table_def

    def __getattr__(self, name: str) -> ColumnRef:
        if name.startswith("_"):
            raise AttributeError(name)
        col = self._columns.get(name)
        if col is None:
            raise AttributeError(f"Table '{self._table_def.name}' has no column '{name}'")
        return ColumnRef(
            table_name=self._table_def.name,
            column_name=col.name,
            schema_name=self._table_def.schema,
        )


def pg_table(name: str, /, *, schema: SchemaRef | None = None, **kwargs: Any) -> TableProxy:
    index_list: list[IndexBuilder] = kwargs.pop("indexes", [])

    columns = []
    for python_name, builder in kwargs.items():
        if not isinstance(builder, ColumnBuilder):
            raise TypeError(
                f"Expected ColumnBuilder for '{python_name}', got {type(builder).__name__}"
            )
        columns.append(builder.to_column_def(python_name))

    indexes = tuple(ib.to_index_def() for ib in index_list)

    table_def = TableDef(
        name=name,
        schema=schema.name if schema else None,
        columns=tuple(columns),
        indexes=indexes,
    )

    return TableProxy(table_def)
