"""Column and index builders with chainable API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydrizzle_orm.ir import ColumnDef, ForeignKeyDef, IndexDef


class SQL:
    __slots__ = ("expr",)

    def __init__(self, expr: str) -> None:
        self.expr = expr

    def __repr__(self) -> str:
        return f"SQL({self.expr!r})"


def sql(expr: str) -> SQL:
    return SQL(expr)


class ColumnBuilder:
    def __init__(
        self,
        col_type: str,
        db_name: str | None = None,
        *,
        enum_name: str | None = None,
    ) -> None:
        self._col_type = col_type
        self._db_name = db_name
        self._nullable = True
        self._default: str | int | float | bool | None = None
        self._default_is_sql = False
        self._primary_key = False
        self._unique = False
        self._is_array = False
        self._references_fn: Callable[[], ColumnRef] | None = None
        self._enum_name = enum_name
        self._varchar_length: int | None = None

    def not_null(self) -> ColumnBuilder:
        self._nullable = False
        return self

    def default(self, value: str | int | float | bool | SQL) -> ColumnBuilder:
        if isinstance(value, SQL):
            self._default = value.expr
            self._default_is_sql = True
        else:
            self._default = value
            self._default_is_sql = False
        return self

    def default_random(self) -> ColumnBuilder:
        self._default = "gen_random_uuid()"
        self._default_is_sql = True
        return self

    def default_now(self) -> ColumnBuilder:
        self._default = "now()"
        self._default_is_sql = True
        return self

    def primary_key(self) -> ColumnBuilder:
        self._primary_key = True
        return self

    def unique(self) -> ColumnBuilder:
        self._unique = True
        return self

    def array(self) -> ColumnBuilder:
        self._is_array = True
        return self

    def references(self, ref_fn: Callable[[], ColumnRef]) -> ColumnBuilder:
        self._references_fn = ref_fn
        return self

    def to_column_def(self, python_name: str) -> ColumnDef:
        db_name = self._db_name if self._db_name is not None else python_name

        fk: ForeignKeyDef | None = None
        if self._references_fn is not None:
            ref = self._references_fn()
            if isinstance(ref, ColumnRef):
                fk = ForeignKeyDef(
                    ref_table=ref.table_name,
                    ref_column=ref.column_name,
                    ref_schema=ref.schema_name,
                )

        return ColumnDef(
            name=db_name,
            python_name=python_name,
            col_type=self._col_type,
            nullable=self._nullable,
            default=self._default,
            default_is_sql=self._default_is_sql,
            primary_key=self._primary_key,
            unique=self._unique,
            is_array=self._is_array,
            references=fk,
            enum_name=self._enum_name,
            varchar_length=self._varchar_length,
        )


@dataclass(frozen=True)
class ColumnRef:
    table_name: str
    column_name: str
    schema_name: str | None = None


class IndexBuilder:
    def __init__(self, name: str, *, unique: bool = False) -> None:
        self._name = name
        self._columns: tuple[str, ...] = ()
        self._unique = unique

    def on(self, *columns: str) -> IndexBuilder:
        self._columns = columns
        return self

    def to_index_def(self) -> IndexDef:
        return IndexDef(
            name=self._name,
            columns=self._columns,
            unique=self._unique,
        )
