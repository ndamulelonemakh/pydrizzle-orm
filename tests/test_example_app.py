from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from pydrizzle_orm.runtime import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_APP = ROOT / "docs" / "example" / "app.py"


def _load_example_app_module():
    module_name = "tests.example_app_module"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, EXAMPLE_APP)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load docs/example/app.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_push_uses_npx_with_required_packages(monkeypatch) -> None:
    example_app = _load_example_app_module()
    client = TestClient(example_app.app)
    out_dir = example_app._HERE / ".test-push-npx"
    out_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
    monkeypatch.setattr(example_app, "_ping_database", lambda _: None)
    monkeypatch.setattr(example_app, "_list_public_tables", lambda _: ["users"])
    monkeypatch.setattr(example_app, "_generate_mode_files", lambda _: (out_dir, 1, 0))
    monkeypatch.setattr(
        example_app,
        "detect_runtime",
        lambda: RuntimeInfo(runner="npx", runner_path="/usr/bin/npx"),
    )

    run_mock = MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="push ok",
            stderr="",
        )
    )
    monkeypatch.setattr(example_app.subprocess, "run", run_mock)

    response = client.post("/api/push/native")

    assert response.status_code == 200
    assert response.json()["tables"] == ["users"]
    run_mock.assert_called_once()
    assert run_mock.call_args.args[0] == [
        "/usr/bin/npx",
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


def test_push_uses_bun_with_local_dependency_bootstrap(monkeypatch) -> None:
    example_app = _load_example_app_module()
    client = TestClient(example_app.app)
    out_dir = example_app._HERE / ".test-push-bun"
    out_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
    monkeypatch.setattr(example_app, "_ping_database", lambda _: None)
    monkeypatch.setattr(example_app, "_list_public_tables", lambda _: ["users"])
    monkeypatch.setattr(example_app, "_generate_mode_files", lambda _: (out_dir, 1, 0))
    monkeypatch.setattr(
        example_app,
        "detect_runtime",
        lambda: RuntimeInfo(runner="bunx", runner_path="/usr/local/bin/bunx"),
    )
    monkeypatch.setattr(example_app.shutil, "which", lambda command: "/usr/local/bin/bun")

    run_mock = MagicMock(
        side_effect=[
            subprocess.CompletedProcess(args=[], returncode=0, stdout="installed", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="push ok", stderr=""),
        ]
    )
    monkeypatch.setattr(example_app.subprocess, "run", run_mock)

    response = client.post("/api/push/native")

    assert response.status_code == 200
    assert response.json()["tables"] == ["users"]
    assert run_mock.call_count == 2
    assert run_mock.call_args_list[0].args[0] == [
        "/usr/local/bin/bun",
        "add",
        "--no-save",
        "drizzle-kit",
        "drizzle-orm",
        "pg",
    ]
    assert run_mock.call_args_list[1].args[0] == [
        "/usr/local/bin/bunx",
        "drizzle-kit",
        "push",
        "--config",
        "drizzle.config.ts",
    ]
