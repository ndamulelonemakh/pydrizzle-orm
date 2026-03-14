"""IR → Drizzle TypeScript codegen engine."""

from __future__ import annotations

from pydrizzle_orm.ir import ColumnDef, EnumDef, TableDef


def generate_typescript(
    tables: list[TableDef],
    enums: list[EnumDef] | None = None,
) -> str:
    ctx = _CodegenContext(tables, enums or [])
    return ctx.generate()


def generate_drizzle_config(
    *,
    schema_path: str = "./drizzle/schema.ts",
    out_dir: str = "./drizzle/migrations",
    dialect: str = "postgresql",
    database_url_env: str = "DATABASE_URL",
    schema_filter: list[str] | None = None,
) -> str:
    lines = [
        'import { defineConfig } from "drizzle-kit";',
        "",
        "export default defineConfig({",
        f'  out: "{out_dir}",',
        f'  dialect: "{dialect}",',
        f'  schema: "{schema_path}",',
        "  dbCredentials: {",
        f"    url: process.env.{database_url_env}!,",
        "  },",
    ]
    if schema_filter:
        items = ", ".join(f"'{s}'" for s in schema_filter)
        lines.append(f"  schemaFilter: [{items}],")
    lines.append("});")
    lines.append("")
    return "\n".join(lines)


def _to_camel(name: str) -> str:
    if "_" in name:
        parts = name.split("_")
        return parts[0].lower() + "".join((p[0].upper() + p[1:]) if p else "" for p in parts[1:])
    if name and name[0].isupper():
        return name[0].lower() + name[1:]
    return name


class _CodegenContext:
    def __init__(self, tables: list[TableDef], enums: list[EnumDef]) -> None:
        self.tables = tables
        self.enums = enums
        self._pg_imports: set[str] = set()
        self._drizzle_imports: set[str] = set()
        self._schemas: dict[str, str] = {}
        self._enum_vars: dict[str, str] = {}

    def generate(self) -> str:
        self._collect_schemas()
        self._collect_enum_vars()

        schema_lines = self._gen_schemas()
        enum_lines = self._gen_enums()
        table_lines = self._gen_tables()

        import_lines = self._gen_imports()

        sections: list[str] = []
        if import_lines:
            sections.append("\n".join(import_lines))
        if schema_lines:
            sections.append("\n".join(schema_lines))
        if enum_lines:
            sections.append("\n".join(enum_lines))
        if table_lines:
            sections.append("\n".join(table_lines))

        return "\n\n".join(sections) + "\n"

    def _collect_schemas(self) -> None:
        all_schemas: set[str] = set()
        for t in self.tables:
            if t.schema:
                all_schemas.add(t.schema)
        for e in self.enums:
            if e.schema:
                all_schemas.add(e.schema)
        for s in sorted(all_schemas):
            if s == "public":
                continue
            self._schemas[s] = _to_camel(s) + "Schema"
            self._pg_imports.add("pgSchema")

    def _collect_enum_vars(self) -> None:
        for e in self.enums:
            self._enum_vars[e.name] = _to_camel(e.name) + "Enum"

    def _gen_imports(self) -> list[str]:
        lines: list[str] = []
        if self._pg_imports:
            items = sorted(self._pg_imports)
            lines.append("import {")
            for item in items:
                lines.append(f"  {item},")
            lines.append("} from 'drizzle-orm/pg-core';")
        if self._drizzle_imports:
            items = sorted(self._drizzle_imports)
            lines.append(f"import {{ {', '.join(items)} }} from 'drizzle-orm';")
        return lines

    def _gen_schemas(self) -> list[str]:
        lines: list[str] = []
        for schema_name, var_name in sorted(self._schemas.items()):
            lines.append(f"export const {var_name} = pgSchema('{schema_name}');")
        return lines

    def _gen_enums(self) -> list[str]:
        lines: list[str] = []
        for e in self.enums:
            var = self._enum_vars[e.name]
            values_str = ", ".join(f"'{v}'" for v in e.values)
            if e.schema and e.schema in self._schemas:
                schema_var = self._schemas[e.schema]
                lines.append(f"export const {var} = {schema_var}.enum('{e.name}', [{values_str}]);")
            else:
                self._pg_imports.add("pgEnum")
                lines.append(f"export const {var} = pgEnum('{e.name}', [{values_str}]);")
        return lines

    def _gen_tables(self) -> list[str]:
        lines: list[str] = []
        for i, t in enumerate(self.tables):
            if i > 0:
                lines.append("")
            lines.extend(self._gen_table(t))
        return lines

    def _gen_table(self, t: TableDef) -> list[str]:
        var_name = _to_camel(t.name)
        lines: list[str] = []

        if t.schema and t.schema in self._schemas:
            constructor = self._schemas[t.schema] + ".table"
        else:
            self._pg_imports.add("pgTable")
            constructor = "pgTable"

        col_lines = []
        for col in t.columns:
            col_lines.append(f"  {_to_camel(col.python_name)}: {self._gen_column(col)},")

        constraint_lines = self._gen_table_constraints(t)

        if constraint_lines:
            lines.append(f"export const {var_name} = {constructor}('{t.name}', {{")
            lines.extend(col_lines)
            lines.append("}, (table) => ({")
            lines.extend(constraint_lines)
            lines.append("}));")
        else:
            lines.append(f"export const {var_name} = {constructor}('{t.name}', {{")
            lines.extend(col_lines)
            lines.append("});")

        return lines

    def _gen_column(self, col: ColumnDef) -> str:
        parts: list[str] = []

        if col.col_type == "enum" and col.enum_name:
            enum_var = self._enum_vars.get(col.enum_name, _to_camel(col.enum_name))
            parts.append(f"{enum_var}('{col.name}')")
        elif col.col_type == "varchar" and col.varchar_length:
            self._pg_imports.add("varchar")
            parts.append(f"varchar('{col.name}', {{ length: {col.varchar_length} }})")
        else:
            self._pg_imports.add(col.col_type)
            parts.append(f"{col.col_type}('{col.name}')")

        if col.primary_key:
            parts.append(".primaryKey()")
        if col.is_array:
            parts.append(".array()")
        if col.default is not None:
            parts.append(self._gen_default(col))
        if not col.nullable:
            parts.append(".notNull()")
        if col.references:
            parts.append(self._gen_reference(col))

        return "".join(parts)

    def _gen_default(self, col: ColumnDef) -> str:
        if col.default_is_sql:
            if col.default == "now()":
                return ".defaultNow()"
            self._drizzle_imports.add("sql")
            return f".default(sql`{col.default}`)"

        if isinstance(col.default, bool):
            return f".default({'true' if col.default else 'false'})"
        if isinstance(col.default, int | float):
            return f".default({col.default})"
        if isinstance(col.default, str):
            return f".default('{col.default}')"
        return ""

    def _gen_reference(self, col: ColumnDef) -> str:
        if not col.references:
            return ""
        ref = col.references
        ref_table_var = _to_camel(ref.ref_table)
        ref_col_js = self._find_js_property(ref.ref_table, ref.ref_column)
        return f".references(() => {ref_table_var}.{ref_col_js})"

    def _find_js_property(self, table_name: str, db_col_name: str) -> str:
        for t in self.tables:
            if t.name == table_name:
                for col in t.columns:
                    if col.name == db_col_name:
                        return _to_camel(col.python_name)
        return _to_camel(db_col_name)

    def _gen_table_constraints(self, t: TableDef) -> list[str]:
        lines: list[str] = []

        for idx in t.indexes:
            cols = ", ".join(f"table.{_to_camel(c)}" for c in idx.columns)
            if idx.unique:
                self._pg_imports.add("unique")
                lines.append(f"  {_to_camel(idx.name)}: unique('{idx.name}').on({cols}),")
            else:
                self._pg_imports.add("index")
                lines.append(f"  {_to_camel(idx.name)}: index('{idx.name}').on({cols}),")

        for col in t.columns:
            if col.unique:
                self._pg_imports.add("unique")
                constraint_name = f"{t.name}_{col.name}_key"
                var_name = _to_camel(col.python_name) + "Unique"
                col_ref = f"table.{_to_camel(col.python_name)}"
                lines.append(f"  {var_name}: unique('{constraint_name}').on({col_ref}),")

        return lines
