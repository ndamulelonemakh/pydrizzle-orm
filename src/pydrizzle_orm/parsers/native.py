"""Native DSL parser — imports modules or packages and collects schema definitions."""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from contextlib import contextmanager, suppress
from pathlib import Path
from types import ModuleType

from pydrizzle_orm.ir import EnumDef, TableDef
from pydrizzle_orm.parsers import ParseResult
from pydrizzle_orm.pg import EnumType, TableProxy


def parse_native_module(module_path: str | Path) -> ParseResult:
    tables: list[TableDef] = []
    enums: list[EnumDef] = []
    seen_tables: set[str] = set()
    seen_enums: set[str] = set()

    for module in _load_native_modules(module_path):
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if isinstance(obj, TableProxy):
                td = obj.table_def
                key = f"{td.schema or ''}.{td.name}"
                if key not in seen_tables:
                    tables.append(td)
                    seen_tables.add(key)
            elif isinstance(obj, EnumType):
                if obj.name not in seen_enums:
                    enums.append(obj.to_enum_def())
                    seen_enums.add(obj.name)

    return ParseResult(tables=tables, enums=enums)


def _load_native_modules(source: str | Path) -> list[ModuleType]:
    raw_source = str(source)
    path = Path(raw_source)

    if path.exists():
        return _load_native_modules_from_path(path.resolve())

    with _prepend_sys_path(Path.cwd()):
        module = importlib.import_module(raw_source)
        return _expand_package_modules(module)


def _load_native_modules_from_path(path: Path) -> list[ModuleType]:
    if path.is_dir():
        import_name, sys_path_entry = _package_import_info(path)
        with _prepend_sys_path(sys_path_entry):
            module = importlib.import_module(import_name)
            return _expand_package_modules(module)

    if path.name == "__init__.py":
        import_name, sys_path_entry = _package_import_info(path.parent)
        with _prepend_sys_path(sys_path_entry):
            module = importlib.import_module(import_name)
            return _expand_package_modules(module)

    import_info = _module_import_info(path)
    if import_info is not None:
        import_name, sys_path_entry = import_info
        with _prepend_sys_path(sys_path_entry):
            module = importlib.import_module(import_name)
            return [module]

    return [_load_module_from_file(path)]


def _load_module_from_file(path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    module_name = f"_pydrizzle_schema_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _expand_package_modules(module: ModuleType) -> list[ModuleType]:
    modules = [module]
    package_path = getattr(module, "__path__", None)
    if package_path is None:
        return modules

    for module_info in pkgutil.walk_packages(package_path, module.__name__ + "."):
        modules.append(importlib.import_module(module_info.name))
    return modules


def _package_import_info(path: Path) -> tuple[str, Path]:
    if not (path / "__init__.py").exists():
        raise FileNotFoundError(f"Schema package not found: {path}")

    parts = [path.name]
    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent
    return ".".join(reversed(parts)), parent


def _module_import_info(path: Path) -> tuple[str, Path] | None:
    parts = [path.stem]
    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent

    if len(parts) == 1:
        return None
    return ".".join(reversed(parts)), parent


@contextmanager
def _prepend_sys_path(path: Path):
    value = str(path)
    if value in sys.path:
        yield
        return

    sys.path.insert(0, value)
    try:
        yield
    finally:
        with suppress(ValueError):
            sys.path.remove(value)
