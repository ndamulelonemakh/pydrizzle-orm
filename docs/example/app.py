from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from pydrizzle_orm.codegen import generate_typescript
from pydrizzle_orm.config import PyDrizzleConfig, load_configs
from pydrizzle_orm.parsers.native import parse_native_module
from pydrizzle_orm.parsers.sqlalchemy import parse_sqlalchemy_module
from pydrizzle_orm.parsers.typescript import parse_typescript_schema
from pydrizzle_orm.runtime import detect_runtime

app = FastAPI(title="pydrizzle-orm demo", docs_url="/api/docs", redoc_url=None)

_HERE = Path(__file__).parent
_CONFIG = _HERE / "pydrizzle.toml"


def _parse_schema(schema_type: str, schema_path: Path):
    if schema_type == "pydrizzle":
        return parse_native_module(schema_path)
    if schema_type == "sqlalchemy":
        return parse_sqlalchemy_module(schema_path)
    if schema_type == "typescript":
        return parse_typescript_schema(schema_path)
    raise ValueError(f"Unsupported schema_type: {schema_type}")


def _resolve_output_dir(config: PyDrizzleConfig, *, multi_target: bool) -> Path:
    out_dir = Path(config.out_dir)
    if multi_target and config.mode and not config.out_dir_explicit:
        out_dir = out_dir / config.mode
    return _HERE / out_dir


def _load_modes() -> dict[str, dict[str, Path | str | bool]]:
    configs = load_configs(_CONFIG)
    multi_target = len(configs) > 1

    result: dict[str, dict[str, Any]] = {}
    for config in configs:
        key = config.mode or "default"
        result[key] = {
            "mode": key,
            "schema": _HERE / config.schema,
            "schema_type": config.schema_type,
            "config": _CONFIG,
            "config_obj": config,
            "database_url_env": config.database_url_env,
            "migrations_dir": config.migrations_dir,
            "out_dir": _resolve_output_dir(config, multi_target=multi_target),
            "can_generate": config.schema_type in {"pydrizzle", "sqlalchemy", "typescript"},
        }
    return result


_MODES = _load_modes()


def _mode_entry(mode: str) -> dict[str, Any]:
    entry = _MODES.get(mode)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown mode: {mode}")
    return entry


def _database_url(entry: dict[str, Any]) -> tuple[str, str]:
    env_name = entry["database_url_env"]
    value = os.getenv(env_name)
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"Database URL not configured. Set {env_name} in your environment.",
        )
    return env_name, value


def _list_public_tables(database_url: str) -> list[str]:
    try:
        import psycopg
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="psycopg is required for database checks in the example app.",
        ) from exc

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        return [row[0] for row in cur.fetchall()]


def _ping_database(database_url: str) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="psycopg is required for database checks in the example app.",
        ) from exc

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")


def _generate_mode_files(entry: dict[str, Any]) -> tuple[Path, int, int]:
    config: PyDrizzleConfig = entry["config_obj"]
    result = _parse_schema(entry["schema_type"], entry["schema"])

    out_dir = entry["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_ts = generate_typescript(result.tables, result.enums)
    schema_path = out_dir / "schema.ts"
    schema_path.write_text(schema_ts, encoding="utf-8")

    schema_filter_line = ""
    if config.schema_filter:
        values = ", ".join(f'"{item}"' for item in config.schema_filter)
        schema_filter_line = f"  schemaFilter: [{values}],\n"

    config_ts = (
        "export default {\n"
        f'  out: "./{config.migrations_dir}",\n'
        f'  dialect: "{config.dialect}",\n'
        '  schema: "./schema.ts",\n'
        "  dbCredentials: {\n"
        f"    url: process.env.{config.database_url_env}!,\n"
        "  },\n"
        f"{schema_filter_line}"
        "};\n"
    )
    drizzle_config = out_dir / "drizzle.config.ts"
    drizzle_config.write_text(config_ts, encoding="utf-8")

    return out_dir, len(result.tables), len(result.enums)


def _install_bun_push_dependencies(cwd: Path) -> None:
    bun = shutil.which("bun")
    if bun is None:
        raise RuntimeError("Bun runtime not found on PATH.")

    subprocess.run(
        [bun, "add", "--no-save", "drizzle-kit", "drizzle-orm", "pg"],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _push_command(out_dir: Path) -> list[str]:
    runtime = detect_runtime()
    if runtime.runner == "bunx":
        _install_bun_push_dependencies(out_dir)
        return [runtime.runner_path, "drizzle-kit", "push", "--config", "drizzle.config.ts"]

    return [
        runtime.runner_path,
        "-y",
        "-p",
        "drizzle-kit",
        "-p",
        "drizzle-orm",
        "-p",
        "pg",
        "drizzle-kit",
        "push",
        "--config",
        "drizzle.config.ts",
    ]


@app.get("/", response_class=HTMLResponse)
def index():
    return (_HERE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/registry")
def get_registry():
    return {
        "config": _CONFIG.name,
        "targets": [
            {
                "mode": entry["mode"],
                "schema_type": entry["schema_type"],
                "schema": entry["schema"].relative_to(_HERE).as_posix(),
                "out_dir": entry["out_dir"].relative_to(_HERE).as_posix(),
                "database_url_env": entry["database_url_env"],
                "can_generate": entry["can_generate"],
            }
            for entry in _MODES.values()
        ],
    }


@app.get("/api/schema/{mode}")
def get_schema_source(mode: str):
    entry = _mode_entry(mode)
    return {
        "source": entry["schema"].read_text(encoding="utf-8"),
        "mode": mode,
        "config": entry["config"].name,
        "schema_type": entry["schema_type"],
        "out_dir": entry["out_dir"].relative_to(_HERE).as_posix(),
    }


@app.post("/api/generate/{mode}")
def generate(mode: str):
    entry = _mode_entry(mode)
    result = _parse_schema(entry["schema_type"], entry["schema"])
    ts = generate_typescript(result.tables, result.enums)
    return {
        "typescript": ts,
        "tables": len(result.tables),
        "enums": len(result.enums),
        "config": entry["config"].name,
        "mode": mode,
        "schema_type": entry["schema_type"],
        "out_dir": entry["out_dir"].relative_to(_HERE).as_posix(),
    }


@app.get("/api/db/health")
def db_health(mode: str = "native"):
    entry = _mode_entry(mode)
    env_name = entry["database_url_env"]
    value = os.getenv(env_name)
    if not value:
        return {
            "alive": False,
            "mode": mode,
            "database_url_env": env_name,
            "detail": f"Set {env_name} to test database connectivity.",
            "tables": [],
        }

    try:
        _ping_database(value)
        tables = _list_public_tables(value)
    except Exception as exc:
        return {
            "alive": False,
            "mode": mode,
            "database_url_env": env_name,
            "detail": str(exc),
            "tables": [],
        }

    return {
        "alive": True,
        "mode": mode,
        "database_url_env": env_name,
        "detail": "Connection successful",
        "tables": tables,
    }


@app.post("/api/push/{mode}")
def push(mode: str):
    entry = _mode_entry(mode)
    database_url_env, database_url = _database_url(entry)

    try:
        _ping_database(database_url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Database connection failed: {exc}") from exc

    out_dir, tables_count, enums_count = _generate_mode_files(entry)

    try:
        result = subprocess.run(
            _push_command(out_dir),
            cwd=out_dir,
            env={**os.environ, database_url_env: database_url},
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.output or "").strip()
        raise HTTPException(
            status_code=422,
            detail=stderr or stdout or "drizzle-kit push failed",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    tables = _list_public_tables(database_url)
    return {
        "ok": True,
        "mode": mode,
        "tables": tables,
        "tables_count": tables_count,
        "enums_count": enums_count,
        "out_dir": out_dir.relative_to(_HERE).as_posix(),
        "stdout": (result.stdout or "").strip(),
    }


class GenerateRequest(BaseModel):
    source: str


@app.post("/api/generate-from-source")
def generate_from_source(body: GenerateRequest):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(body.source)
        f.flush()
        tmp = Path(f.name)

    try:
        result = parse_native_module(tmp)
        ts = generate_typescript(result.tables, result.enums)
        return {
            "typescript": ts,
            "tables": len(result.tables),
            "enums": len(result.enums),
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp.unlink(missing_ok=True)


## FOR DEVELOPMENT ONLY
def dev():
    import uvicorn

    uvicorn.run("app:app", reload=True, port=8000)


if __name__ == "__main__":
    dev()
