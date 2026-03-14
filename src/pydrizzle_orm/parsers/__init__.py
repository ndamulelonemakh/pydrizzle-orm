from __future__ import annotations

from dataclasses import dataclass, field

from pydrizzle_orm.ir import EnumDef, TableDef


@dataclass
class ParseResult:
    tables: list[TableDef] = field(default_factory=list)
    enums: list[EnumDef] = field(default_factory=list)
