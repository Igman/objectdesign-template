"""Locate and load design projects (projects/<name>/design.py)."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DEFAULT_VARIANT = "default"


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "projects").is_dir():
            return parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        )
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd()


def projects_dir() -> Path:
    return repo_root() / "projects"


def list_projects() -> list[str]:
    d = projects_dir()
    return sorted(p.name for p in d.iterdir() if (p / "design.py").exists()) if d.exists() else []


@dataclass
class Project:
    name: str
    path: Path
    module: ModuleType

    @property
    def build_dir(self) -> Path:
        return self.path / "build"

    def variants(self) -> dict:
        """{variant_name: Params}. Always contains at least one entry."""
        declared = getattr(self.module, "VARIANTS", None) or {}
        if declared:
            return dict(declared)
        return {DEFAULT_VARIANT: self.module.Params()}

    def build(self, params) -> dict:
        parts = self.module.build(params)
        if not isinstance(parts, dict) or not parts:
            raise TypeError(f"{self.name}: build() must return a non-empty dict[str, Part]")
        return parts

    def verify(self, parts: dict, params) -> None:
        fn = getattr(self.module, "verify", None)
        if fn is not None:
            fn(parts, params)

    def file_stem(self, variant: str) -> str:
        return self.name if variant == DEFAULT_VARIANT else f"{self.name}_{variant}"


def resolve(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.is_file() and p.name == "design.py":
        return p.parent.resolve()
    if p.is_dir() and (p / "design.py").exists():
        return p.resolve()
    candidate = projects_dir() / name_or_path
    if (candidate / "design.py").exists():
        return candidate
    known = ", ".join(list_projects()) or "(none)"
    raise SystemExit(f"error: no project '{name_or_path}'. Known projects: {known}")


def load(name_or_path: str) -> Project:
    path = resolve(name_or_path)
    design = path / "design.py"
    mod_name = f"od_project_{path.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, design)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path))  # allow project-local helper modules
    try:
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path))
    for attr in ("Params", "build"):
        if not hasattr(module, attr):
            raise SystemExit(f"error: {design} must define `{attr}`")
    return Project(path.name, path, module)
