"""SQLAlchemy parser — imports modules or packages and converts declarative models into IR."""

from __future__ import annotations

import enum
import importlib
import importlib.util
import pkgutil
import sys
from contextlib import contextmanager, suppress
from pathlib import Path
from types import ModuleType
from typing import Any

from pydrizzle_orm.ir import ColumnDef, EnumDef, ForeignKeyDef, IndexDef, TableDef
from pydrizzle_orm.parsers import ParseResult


def parse_sqlalchemy_module(module_path: str | Path) -> ParseResult:
    try:
        from sqlalchemy import Table, UniqueConstraint
    except ImportError as exc:
        raise RuntimeError(
            "SQLAlchemy support requires installing pydrizzle with the sqlalchemy extra"
        ) from exc

    modules = _load_sqlalchemy_modules(module_path)

    declared_tables: dict[tuple[str | None, str], Any] = {}
    metadata_objects: list[Any] = []

    for module in modules:
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            table = getattr(obj, "__table__", None)
            if isinstance(table, Table):
                declared_tables[(table.schema, table.name)] = table
                if table.metadata not in metadata_objects:
                    metadata_objects.append(table.metadata)

    ordered_tables: list[Any] = []
    seen_tables: set[tuple[str | None, str]] = set()
    for metadata in metadata_objects:
        for table in metadata.sorted_tables:
            key = (table.schema, table.name)
            if key in declared_tables and key not in seen_tables:
                ordered_tables.append(declared_tables[key])
                seen_tables.add(key)

    tables: list[TableDef] = []
    enums: list[EnumDef] = []
    seen_enums: set[tuple[str | None, str]] = set()

    for table in ordered_tables:
        unique_constraints, named_unique_columns, implicit_unique_columns = (
            _extract_unique_constraints(table, UniqueConstraint)
        )

        columns: list[ColumnDef] = []
        table_enums: list[EnumDef] = []
        for column in table.columns:
            column_def, enum_defs = _convert_column(
                column,
                named_unique_columns=named_unique_columns,
                implicit_unique_columns=implicit_unique_columns,
            )
            columns.append(column_def)
            table_enums.extend(enum_defs)

        indexes = tuple([*_convert_indexes(table.indexes), *unique_constraints])
        tables.append(
            TableDef(
                name=table.name,
                schema=table.schema,
                columns=tuple(columns),
                indexes=indexes,
            )
        )

        for enum_def in table_enums:
            key = (enum_def.schema, enum_def.name)
            if key not in seen_enums:
                enums.append(enum_def)
                seen_enums.add(key)

    return ParseResult(tables=tables, enums=enums)


def _load_sqlalchemy_modules(source: str | Path) -> list[ModuleType]:
    raw_source = str(source)
    path = Path(raw_source)

    if path.exists():
        return _load_sqlalchemy_modules_from_path(path.resolve())

    importlib.invalidate_caches()
    with _prepend_sys_path(Path.cwd()):
        _purge_module_cache(raw_source)
        module = importlib.import_module(raw_source)
        return _expand_package_modules(module)


def _load_sqlalchemy_modules_from_path(path: Path) -> list[ModuleType]:
    if path.is_dir():
        import_name, sys_path_entry = _package_import_info(path)
        importlib.invalidate_caches()
        with _prepend_sys_path(sys_path_entry):
            _purge_module_cache(import_name)
            module = importlib.import_module(import_name)
            return _expand_package_modules(module)

    if path.name == "__init__.py":
        import_name, sys_path_entry = _package_import_info(path.parent)
        importlib.invalidate_caches()
        with _prepend_sys_path(sys_path_entry):
            _purge_module_cache(import_name)
            module = importlib.import_module(import_name)
            return _expand_package_modules(module)

    import_info = _module_import_info(path)
    if import_info is not None:
        import_name, sys_path_entry = import_info
        importlib.invalidate_caches()
        with _prepend_sys_path(sys_path_entry):
            _purge_module_cache(import_name)
            module = importlib.import_module(import_name)
            return [module]

    return [_load_module_from_file(path)]


def _load_module_from_file(path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    module_name = f"_pydrizzle_sqlalchemy_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _expand_package_modules(module: ModuleType) -> list[ModuleType]:
    modules = [module]
    package_path = getattr(module, "__path__", None)
    if package_path is None:
        return modules

    for module_info in pkgutil.walk_packages(package_path, module.__name__ + "."):
        modules.append(importlib.import_module(module_info.name))
    return modules


def _package_import_info(path: Path) -> tuple[str, Path]:
    if not (path / "__init__.py").exists():
        raise FileNotFoundError(f"Schema package not found: {path}")

    parts = [path.name]
    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent
    return ".".join(reversed(parts)), parent


def _module_import_info(path: Path) -> tuple[str, Path] | None:
    parts = [path.stem]
    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent

    if len(parts) == 1:
        return None
    return ".".join(reversed(parts)), parent


def _purge_module_cache(import_name: str) -> None:
    root = import_name.split(".", 1)[0]
    prefixes = (f"{root}.",)
    for name in list(sys.modules):
        if name == root or name.startswith(prefixes):
            sys.modules.pop(name, None)


@contextmanager
def _prepend_sys_path(path: Path):
    value = str(path)
    if value in sys.path:
        yield
        return

    sys.path.insert(0, value)
    try:
        yield
    finally:
        with suppress(ValueError):
            sys.path.remove(value)


def _convert_column(
    column: Any,
    *,
    named_unique_columns: set[str],
    implicit_unique_columns: set[str],
) -> tuple[ColumnDef, list[EnumDef]]:
    col_type, enum_defs, varchar_length, is_array = _map_column_type(column)
    default, default_is_sql = _extract_default(column)

    return (
        ColumnDef(
            name=column.name,
            python_name=column.key,
            col_type=col_type,
            nullable=column.nullable,
            default=default,
            default_is_sql=default_is_sql,
            primary_key=column.primary_key,
            unique=(column.unique or column.name in implicit_unique_columns)
            and column.name not in named_unique_columns,
            is_array=is_array,
            references=_extract_reference(column),
            enum_name=enum_defs[0].name if enum_defs else None,
            varchar_length=varchar_length,
        ),
        enum_defs,
    )


def _map_column_type(column: Any) -> tuple[str, list[EnumDef], int | None, bool]:
    try:
        from sqlalchemy import Enum as SAEnum
        from sqlalchemy.sql import sqltypes
    except ImportError as exc:
        raise RuntimeError(
            "SQLAlchemy support requires installing pydrizzle with the sqlalchemy extra"
        ) from exc

    sql_type = column.type
    is_array = False

    while isinstance(sql_type, sqltypes.ARRAY):
        is_array = True
        sql_type = sql_type.item_type

    enum_defs: list[EnumDef] = []
    varchar_length: int | None = None

    if isinstance(sql_type, SAEnum):
        enum_name = _infer_enum_name(column)
        values = _enum_values(sql_type)
        enum_defs.append(
            EnumDef(name=enum_name, values=values, schema=sql_type.schema or column.table.schema)
        )
        return "enum", enum_defs, None, is_array

    type_name = type(sql_type).__name__.lower()

    if type_name in {"uuid", "uuidtype", "uuidengine", "uuidv4", "uuidv7", "uuidv1", "uuidv6"}:
        return "uuid", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.Text):
        return "text", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.String):
        if _looks_like_uuid(column):
            return "uuid", enum_defs, None, is_array
        if sql_type.length is not None:
            varchar_length = sql_type.length
            return "varchar", enum_defs, varchar_length, is_array
        return "text", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.Integer):
        if column.primary_key and bool(column.autoincrement):
            return "serial", enum_defs, None, is_array
        return "integer", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.Numeric | sqltypes.Float):
        return "real", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.Boolean):
        return "boolean", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.DateTime):
        return "timestamp", enum_defs, None, is_array
    if type_name == "jsonb":
        return "jsonb", enum_defs, None, is_array
    if isinstance(sql_type, sqltypes.JSON):
        return "json", enum_defs, None, is_array

    raise ValueError(
        f"Unsupported SQLAlchemy type '{type(column.type).__name__}' for column '{column.table.fullname}.{column.name}'"
    )


def _enum_values(sql_type: Any) -> tuple[str, ...]:
    enum_class = getattr(sql_type, "enum_class", None)
    if enum_class is not None and issubclass(enum_class, enum.Enum):
        return tuple(str(member.value) for member in enum_class)
    return tuple(str(value) for value in sql_type.enums)


def _infer_enum_name(column: Any) -> str:
    enum_class = getattr(column.type, "enum_class", None)
    if enum_class is not None:
        return enum_class.__name__
    return f"{column.table.name}_{column.name}_enum"


def _looks_like_uuid(column: Any) -> bool:
    default, default_is_sql = _extract_default(column)
    return bool(default_is_sql and default in {"gen_random_uuid()", "uuid_generate_v4()"})


def _extract_default(column: Any) -> tuple[str | int | float | bool | None, bool]:
    if column.server_default is not None:
        value = _normalize_default_value(column.server_default.arg)
        return value, value is not None

    if column.default is None:
        return None, False

    arg = column.default.arg
    if isinstance(arg, enum.Enum):
        return arg.value, False
    if isinstance(arg, bool | int | float | str):
        return arg, False

    value = _normalize_default_value(arg)
    if value is None:
        return None, False
    if value in {"true", "false"}:
        return value == "true", False
    if value.isdigit():
        return int(value), False
    return value, True


def _normalize_default_value(value: Any) -> str | None:
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return text.strip("()") if text.startswith("((") and text.endswith("))") else text

    rendered = str(value).strip()
    if not rendered or rendered == "None":
        return None
    if rendered.startswith("(") and rendered.endswith(")"):
        rendered = rendered[1:-1]
    return rendered


def _extract_reference(column: Any) -> ForeignKeyDef | None:
    if not column.foreign_keys:
        return None

    foreign_key = next(iter(column.foreign_keys))
    parts = foreign_key.target_fullname.split(".")
    if len(parts) == 3:
        ref_schema, ref_table, ref_column = parts
    elif len(parts) == 2:
        ref_schema = None
        ref_table, ref_column = parts
    else:
        ref_schema = None
        ref_table = foreign_key.column.table.name
        ref_column = foreign_key.column.name

    return ForeignKeyDef(ref_table=ref_table, ref_column=ref_column, ref_schema=ref_schema)


def _convert_indexes(indexes: Any) -> tuple[IndexDef, ...]:
    return tuple(
        IndexDef(
            name=index.name,
            columns=tuple(_expression_name(expression) for expression in index.expressions),
            unique=index.unique,
        )
        for index in sorted(indexes, key=lambda item: item.name or "")
    )


def _extract_unique_constraints(
    table: Any,
    unique_constraint_type: type,
) -> tuple[tuple[IndexDef, ...], set[str], set[str]]:
    named_unique_columns: set[str] = set()
    implicit_unique_columns: set[str] = set()
    constraints: list[IndexDef] = []

    for constraint in table.constraints:
        if not isinstance(constraint, unique_constraint_type):
            continue

        columns = tuple(column.name for column in constraint.columns)
        if len(columns) == 1:
            if constraint.name is None:
                implicit_unique_columns.add(columns[0])
                continue
            named_unique_columns.add(columns[0])

        constraints.append(
            IndexDef(
                name=constraint.name or f"{table.name}_{'_'.join(columns)}_key",
                columns=columns,
                unique=True,
            )
        )

    constraints.sort(key=lambda item: item.name)
    return tuple(constraints), named_unique_columns, implicit_unique_columns


def _expression_name(expression: Any) -> str:
    name = getattr(expression, "name", None)
    if isinstance(name, str):
        return name
    key = getattr(expression, "key", None)
    if isinstance(key, str):
        return key
    raise ValueError(f"Unsupported SQLAlchemy index expression: {expression!r}")
