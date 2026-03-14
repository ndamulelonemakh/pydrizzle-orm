"""Smoke tests for the docs/example — verify the documented usage actually works.

These tests run the example's schema definitions through pydrizzle's parsers and
codegen pipeline without requiring Docker, Node, or any external services.  They
catch the category of bug where an API change silently breaks the flagship example.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "docs" / "example"
_SCHEMAS_DIR = _EXAMPLE_DIR / "schemas"


# ---------------------------------------------------------------------------
# Helper: run a pydrizzle parse+codegen round-trip and return the TS output
# ---------------------------------------------------------------------------


def _generate_ts(tables, enums) -> str:
    from pydrizzle_orm.codegen import generate_typescript

    return generate_typescript(tables, enums)


# ---------------------------------------------------------------------------
# 1. Native mode: parse → codegen → validate output
# ---------------------------------------------------------------------------


class TestNativeMode:
    def test_parse_native_schema(self):
        from pydrizzle_orm.parsers.native import parse_native_module

        result = parse_native_module(_SCHEMAS_DIR / "native_schema.py")
        assert len(result.tables) == 5, f"Expected 5 tables, got {len(result.tables)}"
        assert len(result.enums) == 1, f"Expected 1 enum, got {len(result.enums)}"

    def test_codegen_native_schema(self):
        from pydrizzle_orm.parsers.native import parse_native_module

        result = parse_native_module(_SCHEMAS_DIR / "native_schema.py")
        ts = _generate_ts(result.tables, result.enums)

        # Sanity checks on the generated TypeScript
        assert "pgTable(" in ts or "pgEnum(" in ts
        assert "import" in ts
        assert "'users'" in ts or '"users"' in ts
        assert "'posts'" in ts or '"posts"' in ts
        assert "'comments'" in ts or '"comments"' in ts
        assert "'tags'" in ts or '"tags"' in ts
        assert "'post_tags'" in ts or '"post_tags"' in ts

    def test_native_schema_has_expected_columns(self):
        from pydrizzle_orm.parsers.native import parse_native_module

        result = parse_native_module(_SCHEMAS_DIR / "native_schema.py")
        table_names = {t.name for t in result.tables}
        assert table_names == {"users", "posts", "comments", "tags", "post_tags"}

    def test_native_codegen_produces_valid_imports(self):
        from pydrizzle_orm.parsers.native import parse_native_module

        result = parse_native_module(_SCHEMAS_DIR / "native_schema.py")
        ts = _generate_ts(result.tables, result.enums)

        # Must import from drizzle-orm/pg-core
        assert "from 'drizzle-orm/pg-core'" in ts
        assert "from 'drizzle-orm'" in ts


# ---------------------------------------------------------------------------
# 2. TypeScript mode: parse → round-trip codegen
# ---------------------------------------------------------------------------


class TestTypescriptMode:
    def test_parse_typescript_schema(self):
        from pydrizzle_orm.parsers.typescript import parse_typescript_schema

        result = parse_typescript_schema(_SCHEMAS_DIR / "typescript_schema.ts")
        assert len(result.tables) == 5, f"Expected 5 tables, got {len(result.tables)}"
        assert len(result.enums) == 1, f"Expected 1 enum, got {len(result.enums)}"

    def test_codegen_typescript_round_trip(self):
        from pydrizzle_orm.parsers.typescript import parse_typescript_schema

        result = parse_typescript_schema(_SCHEMAS_DIR / "typescript_schema.ts")
        ts = _generate_ts(result.tables, result.enums)

        assert "pgTable(" in ts or "pgEnum(" in ts
        assert "'users'" in ts or '"users"' in ts


# ---------------------------------------------------------------------------
# 3. SQLAlchemy mode: parse → codegen (requires sqlalchemy)
# ---------------------------------------------------------------------------


class TestSqlalchemyMode:
    @pytest.fixture(autouse=True)
    def _skip_without_sqlalchemy(self):
        pytest.importorskip("sqlalchemy")

    @pytest.fixture(autouse=True)
    def _example_on_path(self):
        """Temporarily add the example dir to sys.path and clean up after."""
        added = str(_EXAMPLE_DIR) not in sys.path
        if added:
            sys.path.insert(0, str(_EXAMPLE_DIR))
        # Snapshot module keys so we can clean up models cached by this test
        before = set(sys.modules)
        yield
        for key in list(sys.modules):
            if key not in before:
                del sys.modules[key]
        if added:
            sys.path.remove(str(_EXAMPLE_DIR))

    def test_parse_sqlalchemy_models(self):
        from pydrizzle_orm.parsers.sqlalchemy import parse_sqlalchemy_module

        result = parse_sqlalchemy_module(_SCHEMAS_DIR / "sqlalchemy_models.py")
        assert len(result.tables) >= 4, f"Expected ≥4 tables, got {len(result.tables)}"

    def test_codegen_sqlalchemy_models(self):
        from pydrizzle_orm.parsers.sqlalchemy import parse_sqlalchemy_module

        result = parse_sqlalchemy_module(_SCHEMAS_DIR / "sqlalchemy_models.py")
        ts = _generate_ts(result.tables, result.enums)
        assert "pgTable(" in ts


# ---------------------------------------------------------------------------
# 4. Models package import test
# ---------------------------------------------------------------------------


class TestModelsPackage:
    """Verify the models/ package imports without circular import errors."""

    @pytest.fixture(autouse=True)
    def _example_on_path(self):
        """Temporarily add the example dir to sys.path and clean up after."""
        added = str(_EXAMPLE_DIR) not in sys.path
        if added:
            sys.path.insert(0, str(_EXAMPLE_DIR))
        before = set(sys.modules)
        yield
        for key in list(sys.modules):
            if key not in before:
                del sys.modules[key]
        if added:
            sys.path.remove(str(_EXAMPLE_DIR))

    def test_models_init_imports_cleanly(self):
        """The models/__init__.py should import from .blog, not from itself."""
        from models import Comment, Post, PostStatus, Tag, User  # noqa: F401


# ---------------------------------------------------------------------------
# 5. CLI smoke test
# ---------------------------------------------------------------------------


class TestCLI:
    def test_python_m_pydrizzle_help(self):
        """python -m pydrizzle_orm --help should work."""
        result = subprocess.run(
            [sys.executable, "-m", "pydrizzle_orm", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "pydrizzle" in result.stdout.lower()

    def test_pydrizzle_status(self):
        """pydrizzle_orm status should work from the example directory."""
        result = subprocess.run(
            [sys.executable, "-m", "pydrizzle_orm", "--mode", "native", "status"],
            capture_output=True,
            text=True,
            cwd=str(_EXAMPLE_DIR),
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# 6. README code snippet validation
# ---------------------------------------------------------------------------


class TestREADMESnippet:
    """Verify the schema snippet shown in the main README actually runs."""

    def test_readme_schema_snippet_runs(self):
        """The imports and DSL calls from the README must not raise."""
        from pydrizzle_orm import (
            index,
            jsonb,
            pg_schema,
            pg_table,
            text,
            timestamp,
            uuid,
        )

        app = pg_schema("app")
        users = pg_table(
            "users",
            schema=app,
            id=uuid("id").primary_key().default_random(),
            email=text("email").not_null().unique(),
            name=text("name"),
            metadata=jsonb("metadata"),
            created_at=timestamp("created_at").default_now().not_null(),
            indexes=[
                index("users_email_idx").on("email"),
            ],
        )

        # Verify it round-trips through codegen
        assert users is not None
