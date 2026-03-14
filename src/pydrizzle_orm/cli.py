from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydrizzle_orm import __version__
from pydrizzle_orm.codegen import generate_drizzle_config, generate_typescript
from pydrizzle_orm.config import PyDrizzleConfig, load_config, load_configs, write_default_config
from pydrizzle_orm.logging import configure_logging, get_logger
from pydrizzle_orm.parsers import ParseResult
from pydrizzle_orm.parsers.native import parse_native_module
from pydrizzle_orm.parsers.sqlalchemy import parse_sqlalchemy_module
from pydrizzle_orm.parsers.typescript import parse_typescript_schema
from pydrizzle_orm.runtime import detect_runtime, run_drizzle_kit

logger = get_logger("cli")


def _parse_schema(config: PyDrizzleConfig) -> ParseResult:
    if config.schema_type == "pydrizzle":
        return parse_native_module(config.schema)
    if config.schema_type == "sqlalchemy":
        return parse_sqlalchemy_module(config.schema)
    if config.schema_type == "typescript":
        return parse_typescript_schema(config.schema)
    logger.error("invalid schema_type", extra={"schema_type": config.schema_type})
    raise SystemExit(1)


def _resolved_out_dir(config: PyDrizzleConfig, *, multi_target: bool) -> Path:
    out_dir = Path(config.out_dir)
    if multi_target and config.mode and not config.out_dir_explicit:
        return out_dir / config.mode
    return out_dir


def _supports_generation(config: PyDrizzleConfig) -> bool:
    return config.schema_type in {"pydrizzle", "sqlalchemy", "typescript"}


def _generate_to_disk(config: PyDrizzleConfig, *, verbose: bool = False) -> Path:
    return _generate_to_disk_for_target(config, verbose=verbose, multi_target=False)


def _generate_to_disk_for_target(
    config: PyDrizzleConfig,
    *,
    verbose: bool = False,
    multi_target: bool = False,
) -> Path:
    result = _parse_schema(config)
    out_dir = _resolved_out_dir(config, multi_target=multi_target)
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_ts = generate_typescript(result.tables, result.enums)
    schema_path = out_dir / "schema.ts"
    schema_path.write_text(schema_ts, encoding="utf-8")

    config_ts = generate_drizzle_config(
        schema_path="./schema.ts",
        out_dir=f"./{config.migrations_dir}",
        dialect=config.dialect,
        database_url_env=config.database_url_env,
        schema_filter=config.schema_filter,
    )
    config_path = out_dir / "drizzle.config.ts"
    config_path.write_text(config_ts, encoding="utf-8")

    if verbose:
        logger.info(
            "generated",
            extra={
                "mode": config.mode or "default",
                "tables": len(result.tables),
                "enums": len(result.enums),
                "schema_path": str(schema_path),
                "config_path": str(config_path),
            },
        )

    return out_dir


def _generate_and_run(
    config: PyDrizzleConfig,
    drizzle_args: list[str],
    *,
    verbose: bool = False,
    dry_run: bool = False,
) -> None:
    out_dir = _generate_to_disk(config, verbose=verbose)
    full_args = [*drizzle_args, "--config", "drizzle.config.ts"]

    if dry_run:
        runtime = detect_runtime()
        logger.info(
            "dry-run",
            extra={
                "runner": runtime.runner,
                "cmd": f"{runtime.runner} drizzle-kit {' '.join(full_args)}",
                "cwd": str(out_dir),
            },
        )
        return

    run_drizzle_kit(full_args, cwd=out_dir, verbose=verbose)


def cmd_init(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    if config_path.exists():
        logger.error("config already exists", extra={"path": str(config_path)})
        raise SystemExit(1)

    schema_file = Path("schema.py")
    write_default_config(config_path, schema_path=str(schema_file))

    created_schema = False
    if not schema_file.exists():
        schema_file.write_text(_SAMPLE_SCHEMA, encoding="utf-8")
        created_schema = True

    logger.info(
        "init complete",
        extra={
            "config": str(config_path),
            "schema": str(schema_file),
            "schema_created": created_schema,
        },
    )


def cmd_generate(args: argparse.Namespace) -> None:
    selected_configs = load_configs(args.config, mode=args.mode)
    configs = [config for config in selected_configs if _supports_generation(config)]

    if not configs:
        _parse_schema(selected_configs[0])

    for config in selected_configs:
        if config in configs:
            continue
        logger.info(
            "skipping generate target",
            extra={
                "mode": config.mode or "default",
                "schema_type": config.schema_type,
            },
        )

    generated: list[str] = []
    skipped: list[str] = []
    multi_target = len(configs) > 1

    for config in configs:
        mode_label = config.mode or "default"
        try:
            out_dir = _generate_to_disk_for_target(
                config,
                verbose=args.verbose,
                multi_target=multi_target,
            )
            generated.append(str(out_dir))
        except RuntimeError as exc:
            logger.warning(
                "skipping target (missing dependency)",
                extra={"mode": mode_label, "reason": str(exc)},
            )
            skipped.append(mode_label)

    if not generated and skipped:
        logger.error(
            "no targets could be generated",
            extra={"skipped": skipped},
        )
        raise SystemExit(1)

    logger.info(
        "generate complete",
        extra={
            "targets": len(generated),
            "out_dirs": generated,
        },
    )


def cmd_push(args: argparse.Namespace) -> None:
    config = load_config(args.config, mode=args.mode)
    _generate_and_run(config, ["push"], verbose=args.verbose, dry_run=args.dry_run)


def cmd_migrate(args: argparse.Namespace) -> None:
    config = load_config(args.config, mode=args.mode)
    _generate_and_run(config, ["generate"], verbose=args.verbose, dry_run=args.dry_run)


def cmd_studio(args: argparse.Namespace) -> None:
    config = load_config(args.config, mode=args.mode)
    _generate_and_run(config, ["studio"], verbose=args.verbose, dry_run=False)


def cmd_status(args: argparse.Namespace) -> None:
    try:
        configs = load_configs(args.config, mode=args.mode)
    except FileNotFoundError:
        logger.error("config missing", extra={"path": args.config})
        raise SystemExit(1) from None

    primary = configs[0]
    details = {
        "version": __version__,
        "config": args.config,
        "dialect": primary.dialect,
        "migrations_dir": primary.migrations_dir,
        "database_url_env": primary.database_url_env,
        "targets": [
            {
                "mode": config.mode or "default",
                "schema": config.schema,
                "schema_type": config.schema_type,
                "out_dir": str(_resolved_out_dir(config, multi_target=len(configs) > 1)),
            }
            for config in configs
        ],
    }
    if primary.available_modes:
        details["available_modes"] = list(primary.available_modes)

    try:
        runtime = detect_runtime()
        details["js_runner"] = runtime.runner
        details["js_runner_path"] = runtime.runner_path
    except RuntimeError:
        details["js_runner"] = "not_found"

    logger.info("status", extra=details)


_SAMPLE_SCHEMA = """\
from pydrizzle_orm.pg import index, pg_table, text, timestamp, uuid

users = pg_table(
    "users",
    id=uuid().primary_key().default_random(),
    email=text().not_null().unique(),
    name=text().not_null(),
    created_at=timestamp("createdAt").default_now().not_null(),
    updated_at=timestamp("updatedAt").default_now().not_null(),
    indexes=[
        index("users_email_idx").on("email"),
    ],
)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pydrizzle-orm", description="Python migrations powered by Drizzle"
    )
    parser.add_argument("--version", action="version", version=f"pydrizzle-orm {__version__}")
    parser.add_argument("--config", default="pydrizzle.toml", help="Config file path")
    parser.add_argument(
        "--mode",
        default=None,
        help="Optional filter for one named entry from [pydrizzle.modes.*]",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logs")
    parser.add_argument("--log-level", default=None, help="Log level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--log-format", choices=["text", "json"], default=None, help="Log format")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create pydrizzle.toml and sample schema")
    sub.add_parser("generate", help="Generate Drizzle TypeScript from Python schema")

    push_p = sub.add_parser("push", help="Generate + push schema to database")
    push_p.add_argument("--dry-run", action="store_true", help="Show command without executing")

    migrate_p = sub.add_parser("migrate", help="Generate SQL migration files")
    migrate_p.add_argument("--dry-run", action="store_true", help="Show command without executing")

    sub.add_parser("studio", help="Launch Drizzle Studio")
    sub.add_parser("status", help="Show config and runtime info")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = args.log_level or ("DEBUG" if args.verbose else None)
    configure_logging(level=level, fmt=args.log_format, stream=sys.stdout, force=True)

    commands = {
        "init": cmd_init,
        "generate": cmd_generate,
        "push": cmd_push,
        "migrate": cmd_migrate,
        "studio": cmd_studio,
        "status": cmd_status,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        raise SystemExit(1)

    handler(args)


if __name__ == "__main__":
    main()
