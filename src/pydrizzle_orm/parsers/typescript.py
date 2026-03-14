"""TypeScript parser — converts a constrained Drizzle schema subset into IR."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from pydrizzle_orm.ir import ColumnDef, EnumDef, ForeignKeyDef, IndexDef, TableDef
from pydrizzle_orm.parsers import ParseResult

_DECLARATION_RE = re.compile(r"(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", re.MULTILINE)
_REFERENCE_RE = re.compile(r"\(\)\s*=>\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
_LENGTH_RE = re.compile(r"length\s*:\s*(\d+)")
_RE_EXPORT_RE = re.compile(
    r"export\s+(?:\*|\{[^}]+\})\s+from\s+['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

_SCALAR_TYPES = {
    "boolean",
    "integer",
    "json",
    "jsonb",
    "real",
    "serial",
    "text",
    "timestamp",
    "uuid",
    "varchar",
}


@dataclass(frozen=True)
class _Declaration:
    name: str
    expression: str


@dataclass(frozen=True)
class _RawColumn:
    property_name: str
    expression: str


@dataclass(frozen=True)
class _RawTable:
    variable_name: str
    table_name: str
    schema_name: str | None
    columns: tuple[_RawColumn, ...]
    constraints: tuple[str, ...]


def parse_typescript_schema(schema_path: str | Path) -> ParseResult:
    path = Path(schema_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    source = "\n\n".join(_load_schema_sources(path))
    declarations = _parse_declarations(source)

    schemas: dict[str, str] = {}
    enum_vars: dict[str, EnumDef] = {}
    raw_tables: list[_RawTable] = []

    for declaration in declarations:
        callee, args = _parse_call(declaration.expression)
        if callee == "pgSchema":
            schemas[declaration.name] = _parse_string_literal(args[0])
            continue
        if callee == "pgEnum" or callee.endswith(".enum"):
            enum_def = _parse_enum_declaration(callee, args, declaration.name, schemas)
            enum_vars[declaration.name] = enum_def
            continue
        if callee == "pgTable" or callee.endswith(".table"):
            raw_tables.append(_parse_table_declaration(declaration.name, callee, args, schemas))

    table_props = {
        raw_table.variable_name: {
            column.property_name: _parse_column_base(column.expression, enum_vars).name
            for column in raw_table.columns
        }
        for raw_table in raw_tables
    }
    table_names = {raw_table.variable_name: raw_table.table_name for raw_table in raw_tables}
    table_schemas = {raw_table.variable_name: raw_table.schema_name for raw_table in raw_tables}

    tables = [
        _build_table_def(raw_table, enum_vars, table_names, table_schemas, table_props)
        for raw_table in raw_tables
    ]

    return ParseResult(tables=tables, enums=list(enum_vars.values()))


def _load_schema_sources(path: Path) -> list[str]:
    return [schema_path.read_text(encoding="utf-8") for schema_path in _discover_schema_files(path)]


def _discover_schema_files(path: Path) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    _collect_schema_files(path, discovered=discovered, seen=seen)
    return discovered


def _collect_schema_files(path: Path, *, discovered: list[Path], seen: set[Path]) -> None:
    resolved = path.resolve()
    if resolved in seen:
        return
    if resolved.is_dir():
        seen.add(resolved)
        for child in _iter_directory_schema_files(resolved):
            _collect_schema_files(child, discovered=discovered, seen=seen)
        return
    if resolved.suffix != ".ts" or resolved.name.endswith(".d.ts"):
        raise ValueError(f"Unsupported TypeScript schema target: {resolved}")

    seen.add(resolved)
    discovered.append(resolved)

    source = resolved.read_text(encoding="utf-8")
    for module_name in _iter_re_export_targets(source):
        target = _resolve_module_target(module_name, base_dir=resolved.parent)
        _collect_schema_files(target, discovered=discovered, seen=seen)


def _iter_directory_schema_files(path: Path) -> list[Path]:
    return sorted(
        child
        for child in path.rglob("*.ts")
        if child.is_file() and not child.name.endswith(".d.ts")
    )


def _iter_re_export_targets(source: str) -> list[str]:
    return [match.group(1) for match in _RE_EXPORT_RE.finditer(source)]


def _resolve_module_target(module_name: str, *, base_dir: Path) -> Path:
    target = (base_dir / module_name).resolve()
    candidates = [target]
    if target.suffix != ".ts":
        candidates.extend((target.with_suffix(".ts"), target / "index.ts"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"TypeScript schema module not found: {module_name}")


def _parse_declarations(source: str) -> list[_Declaration]:
    declarations: list[_Declaration] = []
    position = 0
    while True:
        match = _DECLARATION_RE.search(source, position)
        if match is None:
            break
        name = match.group(1)
        expression_start = match.end()
        expression_end = _find_statement_end(source, expression_start)
        declarations.append(
            _Declaration(name=name, expression=source[expression_start:expression_end].strip())
        )
        position = expression_end + 1
    return declarations


def _find_statement_end(source: str, start: int) -> int:
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    quote: str | None = None
    index = start
    while index < len(source):
        char = source[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == ";" and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            return index
        index += 1
    raise ValueError("Unterminated TypeScript declaration")


def _parse_call(expression: str) -> tuple[str, list[str]]:
    open_paren = expression.find("(")
    if open_paren == -1:
        raise ValueError(f"Expected function call in expression: {expression}")
    close_paren = _find_matching(expression, open_paren, "(", ")")
    callee = expression[:open_paren].strip()
    args = _split_top_level(expression[open_paren + 1 : close_paren])
    return callee, args


def _parse_enum_declaration(
    callee: str,
    args: list[str],
    variable_name: str,
    schemas: dict[str, str],
) -> EnumDef:
    if len(args) != 2:
        raise ValueError(f"Unsupported enum declaration: {callee}({', '.join(args)})")

    schema_name = None
    if callee.endswith(".enum"):
        schema_var = callee.split(".", 1)[0]
        schema_name = schemas.get(schema_var)
        if schema_name is None:
            raise ValueError(f"Unknown schema variable '{schema_var}'")

    enum_name = _parse_string_literal(args[0])
    values = tuple(ast.literal_eval(args[1].strip()))
    return EnumDef(name=enum_name, values=values, schema=schema_name)


def _parse_table_declaration(
    variable_name: str,
    callee: str,
    args: list[str],
    schemas: dict[str, str],
) -> _RawTable:
    if len(args) < 2 or len(args) > 3:
        raise ValueError(f"Unsupported table declaration: {callee}")

    schema_name = None
    if callee.endswith(".table"):
        schema_var = callee.split(".", 1)[0]
        schema_name = schemas.get(schema_var)
        if schema_name is None:
            raise ValueError(f"Unknown schema variable '{schema_var}'")

    table_name = _parse_string_literal(args[0])
    columns = tuple(
        _parse_raw_column(entry) for entry in _parse_object_entries(_extract_object_body(args[1]))
    )
    constraints: tuple[str, ...] = ()
    if len(args) == 3:
        constraints = tuple(_parse_object_entries(_extract_callback_object_body(args[2])))

    return _RawTable(
        variable_name=variable_name,
        table_name=table_name,
        schema_name=schema_name,
        columns=columns,
        constraints=constraints,
    )


def _build_table_def(
    raw_table: _RawTable,
    enum_vars: dict[str, EnumDef],
    table_names: dict[str, str],
    table_schemas: dict[str, str | None],
    table_props: dict[str, dict[str, str]],
) -> TableDef:
    columns = tuple(
        _parse_column_expression(
            raw_column,
            enum_vars=enum_vars,
            table_names=table_names,
            table_schemas=table_schemas,
            table_props=table_props,
        )
        for raw_column in raw_table.columns
    )

    property_to_column = {column.python_name: column.name for column in columns}
    indexes = tuple(
        _parse_constraint_expression(entry, property_to_column) for entry in raw_table.constraints
    )

    return TableDef(
        name=raw_table.table_name,
        schema=raw_table.schema_name,
        columns=columns,
        indexes=indexes,
    )


def _parse_raw_column(entry: str) -> _RawColumn:
    property_name, expression = _split_object_entry(entry)
    return _RawColumn(property_name=property_name, expression=expression)


def _parse_column_base(expression: str, enum_vars: dict[str, EnumDef]) -> ColumnDef:
    property_name = "column"
    raw_column = _RawColumn(property_name=property_name, expression=expression)
    return _parse_column_expression(
        raw_column,
        enum_vars=enum_vars,
        table_names={},
        table_schemas={},
        table_props={},
    )


def _parse_column_expression(
    raw_column: _RawColumn,
    *,
    enum_vars: dict[str, EnumDef],
    table_names: dict[str, str],
    table_schemas: dict[str, str | None],
    table_props: dict[str, dict[str, str]],
) -> ColumnDef:
    base_name, base_args, methods = _parse_chain(raw_column.expression)

    column_name = _parse_string_literal(base_args[0]) if base_args else raw_column.property_name
    col_type = base_name
    enum_name = None
    varchar_length = None

    if base_name in enum_vars:
        col_type = "enum"
        enum_name = enum_vars[base_name].name
    elif base_name not in _SCALAR_TYPES:
        raise ValueError(f"Unsupported TypeScript column type '{base_name}'")

    if base_name == "varchar" and len(base_args) > 1:
        length_match = _LENGTH_RE.search(base_args[1])
        if length_match is not None:
            varchar_length = int(length_match.group(1))

    column = ColumnDef(
        name=column_name,
        python_name=raw_column.property_name,
        col_type=col_type,
        enum_name=enum_name,
        varchar_length=varchar_length,
    )

    for method_name, method_args in methods:
        if method_name == "primaryKey":
            column = _replace_column(column, primary_key=True)
        elif method_name == "array":
            column = _replace_column(column, is_array=True)
        elif method_name == "notNull":
            column = _replace_column(column, nullable=False)
        elif method_name == "unique":
            column = _replace_column(column, unique=True)
        elif method_name == "defaultNow":
            column = _replace_column(column, default="now()", default_is_sql=True)
        elif method_name == "default":
            default, is_sql = _parse_default(method_args[0])
            column = _replace_column(column, default=default, default_is_sql=is_sql)
        elif method_name == "references":
            reference = _parse_reference(method_args[0], table_names, table_schemas, table_props)
            column = _replace_column(column, references=reference)
        else:
            raise ValueError(f"Unsupported TypeScript column modifier '{method_name}'")

    return column


def _parse_constraint_expression(entry: str, property_to_column: dict[str, str]) -> IndexDef:
    _, expression = _split_object_entry(entry)
    base_name, base_args, methods = _parse_chain(expression)
    unique = base_name == "unique"
    if base_name not in {"index", "unique"}:
        raise ValueError(f"Unsupported TypeScript table constraint '{base_name}'")
    if len(base_args) != 1:
        raise ValueError(f"Expected one constraint name argument in '{expression}'")

    columns: tuple[str, ...] = ()
    for method_name, method_args in methods:
        if method_name != "on":
            raise ValueError(f"Unsupported TypeScript table constraint modifier '{method_name}'")
        columns = tuple(_parse_table_property(arg, property_to_column) for arg in method_args)

    return IndexDef(name=_parse_string_literal(base_args[0]), columns=columns, unique=unique)


def _parse_chain(expression: str) -> tuple[str, list[str], list[tuple[str, list[str]]]]:
    expression = " ".join(expression.split())
    open_paren = expression.find("(")
    if open_paren == -1:
        raise ValueError(f"Expected call expression: {expression}")
    close_paren = _find_matching(expression, open_paren, "(", ")")
    base_name = expression[:open_paren].strip()
    base_args = _split_top_level(expression[open_paren + 1 : close_paren])

    methods: list[tuple[str, list[str]]] = []
    index = close_paren + 1
    while index < len(expression):
        if expression[index].isspace():
            index += 1
            continue
        if expression[index] != ".":
            raise ValueError(f"Unexpected token in column chain: {expression[index:]} ")
        index += 1
        method_start = index
        while index < len(expression) and expression[index] not in "(":
            index += 1
        method_name = expression[method_start:index].strip()
        if index >= len(expression) or expression[index] != "(":
            raise ValueError(f"Expected call for method '{method_name}'")
        method_end = _find_matching(expression, index, "(", ")")
        method_args = _split_top_level(expression[index + 1 : method_end])
        methods.append((method_name, method_args))
        index = method_end + 1

    return base_name, base_args, methods


def _parse_default(argument: str) -> tuple[str | int | float | bool, bool]:
    value = argument.strip()
    if value.startswith("sql`") and value.endswith("`"):
        return value[4:-1], True
    if value in {"true", "false"}:
        return value == "true", False
    if value.startswith(("'", '"')):
        return _parse_string_literal(value), False
    if re.fullmatch(r"-?\d+", value):
        return int(value), False
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value), False
    raise ValueError(f"Unsupported TypeScript default expression '{argument}'")


def _parse_reference(
    argument: str,
    table_names: dict[str, str],
    table_schemas: dict[str, str | None],
    table_props: dict[str, dict[str, str]],
) -> ForeignKeyDef:
    match = _REFERENCE_RE.search(argument)
    if match is None:
        raise ValueError(f"Unsupported TypeScript reference '{argument}'")
    table_var, property_name = match.groups()
    db_name = table_props.get(table_var, {}).get(property_name, property_name)
    return ForeignKeyDef(
        ref_table=table_names.get(table_var, table_var),
        ref_column=db_name,
        ref_schema=table_schemas.get(table_var),
    )


def _parse_table_property(argument: str, property_to_column: dict[str, str]) -> str:
    value = argument.strip()
    if not value.startswith("table."):
        raise ValueError(f"Unsupported constraint column reference '{argument}'")
    property_name = value.split(".", 1)[1]
    return property_to_column.get(property_name, property_name)


def _parse_string_literal(value: str) -> str:
    return str(ast.literal_eval(value.strip()))


def _extract_object_body(value: str) -> str:
    text = value.strip()
    if not text.startswith("{"):
        raise ValueError(f"Expected object literal, got '{value}'")
    close = _find_matching(text, 0, "{", "}")
    return text[1:close]


def _extract_callback_object_body(value: str) -> str:
    text = value.strip()
    arrow_index = text.find("=>")
    if arrow_index == -1:
        raise ValueError(f"Expected callback arrow function, got '{value}'")
    text = text[arrow_index + 2 :].strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return _extract_object_body(text)


def _parse_object_entries(body: str) -> list[str]:
    return [entry for entry in _split_top_level(body) if entry.strip()]


def _split_object_entry(entry: str) -> tuple[str, str]:
    index = _find_top_level_separator(entry, ":")
    if index == -1:
        raise ValueError(f"Expected object entry, got '{entry}'")
    return entry[:index].strip(), entry[index + 1 :].strip()


def _split_top_level(text: str) -> list[str]:
    items: list[str] = []
    start = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == "," and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            items.append(text[start:index].strip())
            start = index + 1
        index += 1

    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def _find_top_level_separator(text: str, separator: str) -> int:
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char == separator and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0:
            return index
        index += 1
    return -1


def _find_matching(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"Unmatched '{opening}' in '{text}'")


def _replace_column(column: ColumnDef, **changes: object) -> ColumnDef:
    values = {
        "name": column.name,
        "python_name": column.python_name,
        "col_type": column.col_type,
        "nullable": column.nullable,
        "default": column.default,
        "default_is_sql": column.default_is_sql,
        "primary_key": column.primary_key,
        "unique": column.unique,
        "is_array": column.is_array,
        "references": column.references,
        "enum_name": column.enum_name,
        "varchar_length": column.varchar_length,
    }
    values.update(changes)
    return ColumnDef(**values)
