from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VALID_SCHEMA_TYPES = {"pydrizzle", "sqlalchemy", "typescript"}


@dataclass
class PyDrizzleConfig:
    schema: str
    schema_type: str = "pydrizzle"
    database_url_env: str = "DATABASE_URL"
    dialect: str = "postgresql"
    migrations_dir: str = "migrations"
    schema_filter: list[str] = field(default_factory=lambda: ["public"])
    out_dir: str = ".pydrizzle"
    mode: str | None = None
    available_modes: tuple[str, ...] = ()
    out_dir_explicit: bool = False


def _build_config(
    section: dict,
    *,
    mode: str | None = None,
    available_modes: tuple[str, ...] = (),
    out_dir_explicit: bool = False,
) -> PyDrizzleConfig:
    if "schema" not in section:
        raise ValueError("Missing required 'schema' key in [pydrizzle] section")

    schema_type = section.get("schema_type", "pydrizzle")
    if schema_type not in VALID_SCHEMA_TYPES:
        raise ValueError(
            f"Invalid schema_type '{schema_type}'. Must be one of: {VALID_SCHEMA_TYPES}"
        )

    return PyDrizzleConfig(
        schema=section["schema"],
        schema_type=schema_type,
        database_url_env=section.get("database_url_env", "DATABASE_URL"),
        dialect=section.get("dialect", "postgresql"),
        migrations_dir=section.get("migrations_dir", "migrations"),
        schema_filter=section.get("schema_filter", ["public"]),
        out_dir=section.get("out_dir", ".pydrizzle"),
        mode=mode,
        available_modes=available_modes,
        out_dir_explicit=out_dir_explicit,
    )


def _shared_defaults(section: dict) -> dict:
    return {k: v for k, v in section.items() if k not in {"modes", "active_mode"}}


def load_configs(
    config_path: str | Path = "pydrizzle.toml", *, mode: str | None = None
) -> tuple[PyDrizzleConfig, ...]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    section = data.get("pydrizzle", {})
    modes = section.get("modes", {})
    defaults = _shared_defaults(section)
    available_modes = tuple(sorted(modes)) if isinstance(modes, dict) and modes else ()
    configs: list[PyDrizzleConfig] = []

    if "schema" in defaults:
        configs.append(
            _build_config(
                defaults,
                available_modes=available_modes,
                out_dir_explicit="out_dir" in defaults,
            )
        )

    if isinstance(modes, dict):
        for mode_name in available_modes:
            selected = modes.get(mode_name)
            if not isinstance(selected, dict):
                raise ValueError(f"Invalid config entry for mode '{mode_name}'")
            merged = dict(defaults)
            merged.update(selected)
            configs.append(
                _build_config(
                    merged,
                    mode=mode_name,
                    available_modes=available_modes,
                    out_dir_explicit="out_dir" in selected,
                )
            )

    if mode is not None:
        filtered = tuple(config for config in configs if config.mode == mode)
        if filtered:
            return filtered
        if available_modes:
            raise ValueError(
                f"Unknown mode '{mode}'. Available modes: {', '.join(available_modes)}"
            )
        raise ValueError("No named modes are defined in [pydrizzle.modes.*]")

    if configs:
        return tuple(configs)

    raise ValueError("Missing required 'schema' key in [pydrizzle] section")


def load_config(
    config_path: str | Path = "pydrizzle.toml", *, mode: str | None = None
) -> PyDrizzleConfig:
    configs = load_configs(config_path, mode=mode)
    if len(configs) == 1:
        return configs[0]
    raise ValueError("Multiple config entries are defined; specify --mode or use load_configs()")


def write_default_config(
    config_path: str | Path = "pydrizzle.toml",
    *,
    schema_path: str = "schema.py",
) -> None:
    path = Path(config_path)
    content = f"""[pydrizzle]
schema = "{schema_path}"
schema_type = "pydrizzle"
dialect = "postgresql"
database_url_env = "DATABASE_URL"
migrations_dir = "migrations"
out_dir = ".pydrizzle"
schema_filter = ["public"]
"""
    path.write_text(content, encoding="utf-8")
