from __future__ import annotations

from pathlib import Path

from pydrizzle_orm.parsers.native import parse_native_module


def _write_native_package(tmp_path: Path, package_name: str) -> Path:
    package_root = tmp_path / package_name
    schemas = package_root / "schemas"
    schemas.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (schemas / "__init__.py").write_text("", encoding="utf-8")
    (schemas / "users.py").write_text(
        """\
from pydrizzle_orm.pg import pg_table, text, uuid


users = pg_table(
    "users",
    id=uuid().primary_key().default_random(),
    email=text().not_null(),
)
""",
        encoding="utf-8",
    )
    (schemas / "posts.py").write_text(
        """\
from pydrizzle_orm.pg import pg_enum, pg_table, text, uuid


status = pg_enum("status", ["draft", "published"])

posts = pg_table(
    "posts",
    id=uuid().primary_key().default_random(),
    title=text().not_null(),
    status=status("status").not_null(),
)
""",
        encoding="utf-8",
    )

    return package_root


def test_parse_native_dotted_package_walks_submodules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_native_package(tmp_path, "blogapp")
    monkeypatch.syspath_prepend(str(tmp_path))

    result = parse_native_module("blogapp.schemas")

    assert {table.name for table in result.tables} == {"users", "posts"}
    assert [(enum.name, enum.values) for enum in result.enums] == [
        ("status", ("draft", "published"))
    ]


def test_parse_native_package_directory_walks_submodules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_root = _write_native_package(tmp_path, "shopapp")
    monkeypatch.chdir(tmp_path)

    result = parse_native_module(package_root / "schemas")

    assert {table.name for table in result.tables} == {"users", "posts"}
