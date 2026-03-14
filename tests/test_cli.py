from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pydrizzle_orm.cli import build_parser, main
from pydrizzle_orm.config import load_config, load_configs


def _write_sqlalchemy_schema_and_config(tmp_path: Path) -> Path:
    schema = tmp_path / "models.py"
    schema.write_text(
        """\
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Status(str, enum.Enum):
    draft = "draft"
    published = "published"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="users_email_key"),
        {"schema": "public"},
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = ({"schema": "public"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    status: Mapped[Status] = mapped_column(nullable=False, default=Status.draft)
""",
        encoding="utf-8",
    )

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "{schema}"
schema_type = "sqlalchemy"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


def _write_sqlalchemy_package_and_config(tmp_path: Path) -> Path:
    package_root = tmp_path / "sampleapp"
    models = package_root / "models"
    models.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "base.py").write_text(
        """\
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
""",
        encoding="utf-8",
    )
    (models / "__init__.py").write_text("", encoding="utf-8")
    (models / "users.py").write_text(
        """\
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
""",
        encoding="utf-8",
    )
    (models / "posts.py").write_text(
        """\
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
""",
        encoding="utf-8",
    )

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "sampleapp.models"
schema_type = "sqlalchemy"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


def _write_typescript_schema_and_config(tmp_path: Path) -> Path:
    schema = tmp_path / "schema.ts"
    schema.write_text(
        """\
import { sql } from 'drizzle-orm';
import { index, pgEnum, pgTable, text, timestamp, unique, uuid } from 'drizzle-orm/pg-core';

export const statusEnum = pgEnum('status', ['draft', 'published']);

export const users = pgTable('users', {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    email: text('email').notNull(),
    createdAt: timestamp('created_at').defaultNow().notNull(),
}, (table) => ({
    usersEmailKey: unique('users_email_key').on(table.email),
}));

export const posts = pgTable('posts', {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    userId: uuid('user_id').notNull().references(() => users.id),
    status: statusEnum('status').default('draft').notNull(),
}, (table) => ({
    postsUserIdx: index('posts_user_idx').on(table.userId),
}));
""",
        encoding="utf-8",
    )

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "{schema}"
schema_type = "typescript"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


def _write_typescript_package_and_config(tmp_path: Path, *, use_barrel: bool) -> Path:
    schema_root = tmp_path / "schemas"
    tables_dir = schema_root / "tables"
    tables_dir.mkdir(parents=True)

    (schema_root / "status.ts").write_text(
        """\
export const statusEnum = pgEnum('status', ['draft', 'published']);
""",
        encoding="utf-8",
    )
    (tables_dir / "users.ts").write_text(
        """\
export const users = pgTable('users', {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    email: text('email').notNull(),
});
""",
        encoding="utf-8",
    )
    (tables_dir / "posts.ts").write_text(
        """\
export const posts = pgTable('posts', {
    id: uuid('id').primaryKey().default(sql`gen_random_uuid()`),
    userId: uuid('user_id').notNull().references(() => users.id),
    status: statusEnum('status').default('draft').notNull(),
}, (table) => ({
    postsUserIdx: index('posts_user_idx').on(table.userId),
}));
""",
        encoding="utf-8",
    )

    schema_target = schema_root
    if use_barrel:
        (schema_root / "index.ts").write_text(
            """\
export * from './status';
export * from './tables/users';
export * from './tables/posts';
""",
            encoding="utf-8",
        )
        schema_target = schema_root / "index.ts"

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "{schema_target}"
schema_type = "typescript"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


def _write_schema_and_config(tmp_path: Path) -> Path:
    schema = tmp_path / "schema.py"
    schema.write_text(
        """\
from pydrizzle_orm.pg import pg_table, uuid, text, timestamp, index
from pydrizzle_orm.types import sql

users = pg_table(
    "users",
    id=uuid().primary_key().default_random(),
    email=text().not_null(),
    created_at=timestamp("createdAt").default_now().not_null(),
    indexes=[index("users_email_idx").on("email")],
)
""",
        encoding="utf-8",
    )

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "{schema}"
schema_type = "pydrizzle"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


def _write_native_package_and_config(tmp_path: Path) -> Path:
    package_root = tmp_path / "nativeapp"
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
from pydrizzle_orm.pg import pg_table, text, uuid


posts = pg_table(
    "posts",
    id=uuid().primary_key().default_random(),
    title=text().not_null(),
)
""",
        encoding="utf-8",
    )

    config = tmp_path / "pydrizzle.toml"
    config.write_text(
        f"""\
[pydrizzle]
schema = "nativeapp.schemas"
schema_type = "pydrizzle"
dialect = "postgresql"
out_dir = "{tmp_path / ".pydrizzle"}"
""",
        encoding="utf-8",
    )
    return config


class TestBuildParser:
    def test_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit, match="0"):
            parser.parse_args(["--version"])
        assert "pydrizzle-orm" in capsys.readouterr().out

    def test_requires_subcommand(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_all_subcommands_parse(self) -> None:
        parser = build_parser()
        for cmd in ("init", "generate", "push", "migrate", "studio", "status"):
            args = parser.parse_args([cmd])
            assert args.command == cmd

    def test_dry_run_on_push(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["push", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_on_migrate(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["migrate", "--dry-run"])
        assert args.dry_run is True

    def test_custom_config_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--config", "custom.toml", "status"])
        assert args.config == "custom.toml"

    def test_mode_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--mode", "native", "status"])
        assert args.mode == "native"

    def test_verbose_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["-v", "generate"])
        assert args.verbose is True


class TestCmdInit:
    def test_creates_config_and_schema(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pydrizzle.toml"
        os.chdir(tmp_path)

        main(["--config", str(config_path), "init"])

        assert config_path.exists()
        assert (tmp_path / "schema.py").exists()

        cfg = load_config(config_path)
        assert cfg.schema == "schema.py"
        assert cfg.schema_type == "pydrizzle"

    def test_refuses_existing_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pydrizzle.toml"
        config_path.write_text("[pydrizzle]\nschema = 'x.py'\n", encoding="utf-8")

        with pytest.raises(SystemExit):
            main(["--config", str(config_path), "init"])

    def test_does_not_overwrite_existing_schema(self, tmp_path: Path) -> None:
        config_path = tmp_path / "pydrizzle.toml"
        schema_path = tmp_path / "schema.py"
        schema_path.write_text("# my existing schema\n", encoding="utf-8")
        os.chdir(tmp_path)

        main(["--config", str(config_path), "init"])

        assert config_path.exists()
        assert schema_path.read_text() == "# my existing schema\n"


class TestCmdGenerate:
    def test_generates_typescript_files(self, tmp_path: Path) -> None:
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "generate"])

        out_dir = tmp_path / ".pydrizzle"
        assert (out_dir / "schema.ts").exists()
        assert (out_dir / "drizzle.config.ts").exists()

        schema_ts = (out_dir / "schema.ts").read_text()
        assert "pgTable" in schema_ts
        assert "export const users" in schema_ts
        assert "uuid('id')" in schema_ts

    def test_generates_valid_drizzle_config(self, tmp_path: Path) -> None:
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "generate"])

        config_ts = (tmp_path / ".pydrizzle" / "drizzle.config.ts").read_text()
        assert "defineConfig" in config_ts
        assert 'dialect: "postgresql"' in config_ts
        assert "process.env.DATABASE_URL!" in config_ts

    def test_generates_from_named_mode(self, tmp_path: Path) -> None:
        schema = tmp_path / "schema.py"
        schema.write_text(
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
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            f"""\
[pydrizzle]
out_dir = "{tmp_path / ".pydrizzle"}"

[pydrizzle.modes.native]
schema = "{schema}"
schema_type = "pydrizzle"

[pydrizzle.modes.sqlalchemy]
schema = "models.py"
schema_type = "sqlalchemy"
""",
            encoding="utf-8",
        )

        main(["--config", str(config), "--mode", "native", "generate"])

        assert (tmp_path / ".pydrizzle" / "schema.ts").exists()

    def test_native_generate_from_dotted_package(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config = _write_native_package_and_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "export const users = pgTable('users'" in output
        assert "export const posts = pgTable('posts'" in output

    def test_generates_all_named_modes(self, tmp_path: Path) -> None:
        core_schema = tmp_path / "core_schema.py"
        core_schema.write_text(
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
        audit_schema = tmp_path / "audit_schema.py"
        audit_schema.write_text(
            """\
from pydrizzle_orm.pg import integer, pg_table

events = pg_table(
    "events",
    id=integer().primary_key(),
)
""",
            encoding="utf-8",
        )
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            f"""\
[pydrizzle]
out_dir = "{tmp_path / ".pydrizzle"}"

[pydrizzle.modes.core]
schema = "{core_schema}"
schema_type = "pydrizzle"

[pydrizzle.modes.audit]
schema = "{audit_schema}"
schema_type = "pydrizzle"
""",
            encoding="utf-8",
        )

        main(["--config", str(config), "generate"])

        assert (tmp_path / ".pydrizzle" / "core" / "schema.ts").exists()
        assert (tmp_path / ".pydrizzle" / "audit" / "schema.ts").exists()

    def test_verbose_output(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "-v", "generate"])

        captured = capsys.readouterr().out
        assert "generated" in captured
        assert "schema.ts" in captured


class TestDryRun:
    @patch("pydrizzle_orm.cli.run_drizzle_kit")
    @patch("pydrizzle_orm.cli.detect_runtime")
    def test_push_dry_run_does_not_invoke_subprocess(
        self,
        mock_detect: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from pydrizzle_orm.runtime import RuntimeInfo

        mock_detect.return_value = RuntimeInfo(runner="bunx", runner_path="/usr/bin/bunx")
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "push", "--dry-run"])

        mock_run.assert_not_called()
        captured = capsys.readouterr().out
        assert "dry-run" in captured
        assert "bunx" in captured

    @patch("pydrizzle_orm.cli.run_drizzle_kit")
    @patch("pydrizzle_orm.cli.detect_runtime")
    def test_migrate_dry_run_does_not_invoke_subprocess(
        self,
        mock_detect: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        from pydrizzle_orm.runtime import RuntimeInfo

        mock_detect.return_value = RuntimeInfo(runner="npx", runner_path="/usr/bin/npx")
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "migrate", "--dry-run"])

        mock_run.assert_not_called()


class TestCmdStatus:
    def test_status_shows_config_info(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config_path = _write_schema_and_config(tmp_path)

        main(["--config", str(config_path), "status"])

        captured = capsys.readouterr().out
        assert "status" in captured
        assert "postgresql" in captured
        assert "DATABASE_URL" in captured

    def test_status_shows_mode_info(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            """\
[pydrizzle]

[pydrizzle.modes.native]
schema = "schema.py"
schema_type = "pydrizzle"

[pydrizzle.modes.typescript]
schema = "schema.ts"
schema_type = "typescript"
""",
            encoding="utf-8",
        )

        main(["--config", str(config), "status"])

        captured = capsys.readouterr().out
        assert "native" in captured
        assert "typescript" in captured
        assert "targets" in captured

    def test_status_missing_config(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main(["--config", str(tmp_path / "nonexistent.toml"), "status"])

        captured = capsys.readouterr().out
        assert "config missing" in captured


class TestErrorPaths:
    def test_loads_named_mode(self, tmp_path: Path) -> None:
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            """\
[pydrizzle]
database_url_env = "APP_DB"

[pydrizzle.modes.native]
schema = "schema.py"
schema_type = "pydrizzle"

[pydrizzle.modes.sqlalchemy]
schema = "models.py"
schema_type = "sqlalchemy"
out_dir = ".pydrizzle-sqlalchemy"
""",
            encoding="utf-8",
        )

        cfg = load_config(config, mode="sqlalchemy")

        assert cfg.mode == "sqlalchemy"
        assert cfg.schema == "models.py"
        assert cfg.schema_type == "sqlalchemy"
        assert cfg.database_url_env == "APP_DB"
        assert cfg.out_dir == ".pydrizzle-sqlalchemy"
        assert cfg.available_modes == ("native", "sqlalchemy")

    def test_mode_flag_overrides_active_mode(self, tmp_path: Path) -> None:
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            """\
[pydrizzle.modes.native]
schema = "schema.py"
schema_type = "pydrizzle"

[pydrizzle.modes.sqlalchemy]
schema = "models.py"
schema_type = "sqlalchemy"
""",
            encoding="utf-8",
        )

        cfg = load_config(config, mode="native")

        assert cfg.mode == "native"
        assert cfg.schema == "schema.py"
        assert cfg.schema_type == "pydrizzle"

    def test_load_configs_returns_all_entries(self, tmp_path: Path) -> None:
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            """\
[pydrizzle.modes.native]
schema = "schema.py"
schema_type = "pydrizzle"

[pydrizzle.modes.typescript]
schema = "schema.ts"
schema_type = "typescript"
""",
            encoding="utf-8",
        )

        configs = load_configs(config)

        assert len(configs) == 2
        assert {cfg.mode for cfg in configs} == {"native", "typescript"}

    def test_load_config_requires_explicit_mode_for_multiple_entries(self, tmp_path: Path) -> None:
        config = tmp_path / "pydrizzle.toml"
        config.write_text(
            """\
[pydrizzle.modes.native]
schema = "schema.py"
schema_type = "pydrizzle"

[pydrizzle.modes.typescript]
schema = "schema.ts"
schema_type = "typescript"
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="specify --mode"):
            load_config(config)

    def test_sqlalchemy_generate(self, tmp_path: Path) -> None:
        pytest.importorskip("sqlalchemy")
        config = _write_sqlalchemy_schema_and_config(tmp_path)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "export const users = pgTable('users'" in output
        assert "unique('users_email_key').on(table.email)" in output
        assert "statusEnum('status').default('draft').notNull()" in output
        assert ".notNull().references(() => users.id)" in output

    def test_sqlalchemy_generate_from_dotted_package(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pytest.importorskip("sqlalchemy")
        config = _write_sqlalchemy_package_and_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "export const users = pgTable('users'" in output
        assert "export const posts = pgTable('posts'" in output
        assert "text('author_id').notNull().references(() => users.id)" in output

    def test_typescript_generate(self, tmp_path: Path) -> None:
        config = _write_typescript_schema_and_config(tmp_path)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "pgEnum('status', ['draft', 'published'])" in output
        assert "uuid('user_id').notNull().references(() => users.id)" in output
        assert "statusEnum('status').default('draft').notNull()" in output

    def test_typescript_generate_from_barrel_file(self, tmp_path: Path) -> None:
        config = _write_typescript_package_and_config(tmp_path, use_barrel=True)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "export const users = pgTable('users'" in output
        assert "export const posts = pgTable('posts'" in output
        assert "uuid('user_id').notNull().references(() => users.id)" in output

    def test_typescript_generate_from_directory(self, tmp_path: Path) -> None:
        config = _write_typescript_package_and_config(tmp_path, use_barrel=False)

        main(["--config", str(config), "generate"])

        output = (tmp_path / ".pydrizzle" / "schema.ts").read_text(encoding="utf-8")
        assert "pgEnum('status', ['draft', 'published'])" in output
        assert "index('posts_user_idx').on(table.userId)" in output
