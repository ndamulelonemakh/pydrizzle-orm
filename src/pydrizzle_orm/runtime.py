from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydrizzle_orm.logging import get_logger

JsRunner = Literal["bunx", "npx"]
logger = get_logger("runtime")
JS_RUNNER_ENV = "PYDRIZZLE_JS_RUNNER"


@dataclass(frozen=True)
class RuntimeInfo:
    runner: JsRunner
    runner_path: str


def detect_runtime() -> RuntimeInfo:
    preferred = os.getenv(JS_RUNNER_ENV)
    if preferred:
        if preferred not in {"bunx", "npx"}:
            raise RuntimeError(f"Invalid {JS_RUNNER_ENV}={preferred!r}. Expected 'bunx' or 'npx'.")
        resolved = shutil.which(preferred)
        if resolved is None:
            raise RuntimeError(f"Configured JavaScript runner '{preferred}' was not found on PATH.")
        return RuntimeInfo(runner=preferred, runner_path=resolved)

    bunx = shutil.which("bunx")
    if bunx is not None:
        return RuntimeInfo(runner="bunx", runner_path=bunx)

    npx = shutil.which("npx")
    if npx is not None:
        return RuntimeInfo(runner="npx", runner_path=npx)

    raise RuntimeError(
        "No JavaScript runtime found. Install Bun (https://bun.sh) "
        "or Node.js (https://nodejs.org) to use pydrizzle."
    )


def run_drizzle_kit(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    verbose: bool = False,
) -> subprocess.CompletedProcess[str]:
    runtime = detect_runtime()

    cmd = [runtime.runner_path, "drizzle-kit", *args]

    run_env = {**os.environ, **(env or {})}

    if verbose:
        logger.debug("exec", extra={"cmd": " ".join(cmd), "cwd": str(cwd)})

    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=run_env,
        check=True,
        text=True,
        capture_output=not verbose,
    )

    if not verbose and result.stderr and "error" in result.stderr.lower():
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            output=result.stdout,
            stderr=result.stderr,
        )

    return result
