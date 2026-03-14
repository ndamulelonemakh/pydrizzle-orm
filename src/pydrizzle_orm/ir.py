"""Schema Intermediate Representation — the core data model all parsers produce."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaRef:
    name: str


@dataclass(frozen=True)
class ForeignKeyDef:
    ref_table: str
    ref_column: str
    ref_schema: str | None = None


@dataclass(frozen=True)
class ColumnDef:
    name: str
    python_name: str
    col_type: str
    nullable: bool = True
    default: str | int | float | bool | None = None
    default_is_sql: bool = False
    primary_key: bool = False
    unique: bool = False
    is_array: bool = False
    references: ForeignKeyDef | None = None
    enum_name: str | None = None
    varchar_length: int | None = None


@dataclass(frozen=True)
class IndexDef:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class EnumDef:
    name: str
    values: tuple[str, ...]
    schema: str | None = None


@dataclass(frozen=True)
class TableDef:
    name: str
    schema: str | None = None
    columns: tuple[ColumnDef, ...] = ()
    indexes: tuple[IndexDef, ...] = ()
