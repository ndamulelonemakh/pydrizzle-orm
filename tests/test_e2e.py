from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

from pydrizzle_orm.cli import main
from pydrizzle_orm.runtime import detect_runtime

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "docs" / "example"


def _docker_host() -> str | None:
    if shutil.which("docker") is None:
        return None
    result = subprocess.run(
        ["docker", "context", "inspect"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    payload = json.loads(result.stdout)
    if not payload:
        return None
    return payload[0].get("Endpoints", {}).get("docker", {}).get("Host")


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _install_drizzle_kit(project_dir: Path) -> None:
    subprocess.run(
        ["npm", "install", "--no-save", "drizzle-kit", "drizzle-orm", "pg"],
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.e2e
def test_example_native_schema_pushes_to_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not available")

    try:
        detect_runtime()
    except RuntimeError as exc:
        pytest.skip(str(exc))

    docker_host = _docker_host()
    if docker_host:
        monkeypatch.setenv("DOCKER_HOST", docker_host)
    monkeypatch.setenv("TESTCONTAINERS_RYUK_DISABLED", "true")
    monkeypatch.setenv("PYDRIZZLE_JS_RUNNER", "npx")

    example_copy = tmp_path / "example"
    shutil.copytree(EXAMPLE_DIR / "schemas", example_copy / "schemas")
    shutil.copy2(EXAMPLE_DIR / "pydrizzle.toml", example_copy / "pydrizzle.toml")
    _install_drizzle_kit(example_copy)

    with PostgresContainer(
        "postgres:16-alpine",
        username="postgres",
        password="postgres",
        dbname="pydrizzle_example",
    ) as postgres:
        database_url = postgres.get_connection_url()
        psycopg_url = database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        monkeypatch.chdir(example_copy)
        monkeypatch.setenv("DATABASE_URL", psycopg_url)
        monkeypatch.setenv("CI", "1")

        main(["--config", "pydrizzle.toml", "--mode", "native", "push"])

        out_dir = example_copy / ".pydrizzle"
        assert (out_dir / "schema.ts").exists()
        assert (out_dir / "drizzle.config.ts").exists()

        with psycopg.connect(psycopg_url) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = 'public'
                    """
                ).fetchall()
            }
            assert {"users", "posts", "comments", "tags", "post_tags"}.issubset(tables)

            enum_names = {
                row[0]
                for row in conn.execute(
                    """
                    select t.typname
                    from pg_type t
                    join pg_namespace n on n.oid = t.typnamespace
                    where n.nspname = 'public' and t.typtype = 'e'
                    """
                ).fetchall()
            }
            assert "post_status" in enum_names

            post_columns = {
                row[0]
                for row in conn.execute(
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema = 'public' and table_name = 'posts'
                    """
                ).fetchall()
            }
            assert {
                "id",
                "title",
                "slug",
                "body",
                "status",
                "author_id",
                "created_at",
            } == post_columns
