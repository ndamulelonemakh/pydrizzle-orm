from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pydrizzle_orm.runtime import RuntimeInfo, detect_runtime, run_drizzle_kit


class TestDetectRuntime:
    def test_honors_explicit_runner_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYDRIZZLE_ORM_JS_RUNNER", "npx")
        with patch("pydrizzle_orm.runtime.shutil.which") as mock_which:

            def _which(cmd: str) -> str | None:
                if cmd == "npx":
                    return "/usr/local/bin/npx"
                return None

            mock_which.side_effect = _which
            info = detect_runtime()
        assert info.runner == "npx"
        assert info.runner_path == "/usr/local/bin/npx"

    def test_rejects_invalid_runner_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYDRIZZLE_ORM_JS_RUNNER", "node")

        with pytest.raises(RuntimeError, match="Invalid PYDRIZZLE_ORM_JS_RUNNER"):
            detect_runtime()

    def test_prefers_bunx_when_available(self) -> None:
        with patch("pydrizzle_orm.runtime.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/local/bin/bunx" if cmd == "bunx" else None
            info = detect_runtime()
        assert info.runner == "bunx"
        assert info.runner_path == "/usr/local/bin/bunx"

    def test_falls_back_to_npx(self) -> None:
        with patch("pydrizzle_orm.runtime.shutil.which") as mock_which:

            def _which(cmd: str) -> str | None:
                if cmd == "bunx":
                    return None
                if cmd == "npx":
                    return "/usr/local/bin/npx"
                return None

            mock_which.side_effect = _which
            info = detect_runtime()
        assert info.runner == "npx"
        assert info.runner_path == "/usr/local/bin/npx"

    def test_raises_when_nothing_found(self) -> None:
        with (
            patch("pydrizzle_orm.runtime.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="No JavaScript runtime found"),
        ):
            detect_runtime()

    def test_bunx_takes_priority_over_npx(self) -> None:
        with patch("pydrizzle_orm.runtime.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: {
                "bunx": "/opt/bun/bunx",
                "npx": "/usr/bin/npx",
            }.get(cmd)
            info = detect_runtime()
        assert info.runner == "bunx"


class TestRunDrizzleKit:
    @patch("pydrizzle_orm.runtime.detect_runtime")
    @patch("pydrizzle_orm.runtime.subprocess.run")
    def test_invokes_correct_command(
        self, mock_run: MagicMock, mock_detect: MagicMock, tmp_path: Path
    ) -> None:
        mock_detect.return_value = RuntimeInfo(runner="bunx", runner_path="/usr/bin/bunx")
        mock_run.return_value = MagicMock(returncode=0)

        run_drizzle_kit(["push", "--config", "drizzle.config.ts"], cwd=tmp_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd == ["/usr/bin/bunx", "drizzle-kit", "push", "--config", "drizzle.config.ts"]
        assert call_args[1]["cwd"] == tmp_path
        assert call_args[1]["check"] is True

    @patch("pydrizzle_orm.runtime.detect_runtime")
    @patch("pydrizzle_orm.runtime.subprocess.run")
    def test_npx_fallback_command(
        self, mock_run: MagicMock, mock_detect: MagicMock, tmp_path: Path
    ) -> None:
        mock_detect.return_value = RuntimeInfo(runner="npx", runner_path="/usr/bin/npx")
        mock_run.return_value = MagicMock(returncode=0)

        run_drizzle_kit(["generate"], cwd=tmp_path)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/npx"
        assert cmd[1] == "drizzle-kit"

    @patch("pydrizzle_orm.runtime.detect_runtime")
    @patch("pydrizzle_orm.runtime.subprocess.run")
    def test_extra_env_merged(
        self, mock_run: MagicMock, mock_detect: MagicMock, tmp_path: Path
    ) -> None:
        mock_detect.return_value = RuntimeInfo(runner="bunx", runner_path="/usr/bin/bunx")
        mock_run.return_value = MagicMock(returncode=0)

        run_drizzle_kit(["push"], cwd=tmp_path, env={"DATABASE_URL": "postgres://localhost/test"})

        run_env = mock_run.call_args[1]["env"]
        assert run_env["DATABASE_URL"] == "postgres://localhost/test"

    @patch("pydrizzle_orm.runtime.detect_runtime")
    @patch("pydrizzle_orm.runtime.subprocess.run")
    def test_verbose_prints_command(
        self,
        mock_run: MagicMock,
        mock_detect: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_detect.return_value = RuntimeInfo(runner="bunx", runner_path="/usr/bin/bunx")
        mock_run.return_value = MagicMock(returncode=0)

        run_drizzle_kit(["studio"], cwd=tmp_path, verbose=True)

        assert mock_run.call_args[1]["capture_output"] is False

    @patch("pydrizzle_orm.runtime.detect_runtime")
    @patch("pydrizzle_orm.runtime.subprocess.run")
    def test_quiet_mode_captures_output(
        self, mock_run: MagicMock, mock_detect: MagicMock, tmp_path: Path
    ) -> None:
        mock_detect.return_value = RuntimeInfo(runner="bunx", runner_path="/usr/bin/bunx")
        mock_run.return_value = MagicMock(returncode=0)

        run_drizzle_kit(["push"], cwd=tmp_path, verbose=False)

        assert mock_run.call_args[1]["capture_output"] is True
