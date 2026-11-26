"""`od`: the ObjectDesign command-line tool.

    uv run od setup                       check this machine is ready
    uv run od list                        list projects
    uv run od new <name> [--from-stl F]   scaffold a project
    uv run od check <project> [--json]    validate geometry + verify()
    uv run od view <project> [--variant V] show in the OCP CAD Viewer ('all' = side by side)
    uv run od watch [project]             live preview: re-show on save / viewer open
    uv run od render <project>            contact-sheet PNG(s) for review
    uv run od build <project>             export 3MF/STEP/STL to build/
    uv run od release <project>           export to exports/, commit, tag <project>/vN
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from od import project as prj


def _variants(p: prj.Project, only: str | None) -> dict:
    vs = p.variants()
    if only:
        if only not in vs:
            raise SystemExit(f"error: variant '{only}' not in {list(vs)}")
        return {only: vs[only]}
    return vs


def _git(*args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=prj.repo_root(), capture_output=True, text=True)
    if check and out.returncode != 0:
        raise SystemExit(f"error: git {' '.join(args)} failed:\n{out.stderr.strip()}")
    return out.stdout.strip()


# --- commands -----------------------------------------------------------------


def cmd_setup(args) -> int:
    ok = True

    def line(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"  [{'ok' if good else '!!'}] {label}" + (f": {detail}" if detail else ""))

    print(f"ObjectDesign setup check ({platform.system()} {platform.machine()})")
    line(sys.version_info[:2] == (3, 14), "Python", sys.version.split()[0])
    from od import printer

    line(True, "printer.toml", printer.summary())
    try:
        import build123d

        line(True, "build123d", build123d.__version__)
    except Exception as e:  # noqa: BLE001
        line(False, "build123d", str(e))
    for mod in ("ocp_vscode", "manifold3d", "trimesh", "PIL"):
        try:
            __import__(mod)
            line(True, mod)
        except Exception as e:  # noqa: BLE001
            line(False, mod, str(e))

    lfs = shutil.which("git-lfs")
    line(bool(lfs), "git-lfs installed", lfs or "install: macOS `brew install git-lfs`; Windows: included with Git for Windows")
    if lfs:
        subprocess.run(["git", "lfs", "install", "--local"], cwd=prj.repo_root(), capture_output=True)
        hooked = bool(_git("config", "--get", "filter.lfs.process", check=False))
        line(hooked, "git-lfs enabled for this repo")

    code = shutil.which("code")
    if code:
        exts = subprocess.run([code, "--list-extensions"], capture_output=True, text=True).stdout.lower()
        line("bernhard-42.ocp-cad-viewer" in exts, "VS Code: OCP CAD Viewer extension",
             "" if "bernhard-42.ocp-cad-viewer" in exts else "code --install-extension bernhard-42.ocp-cad-viewer")
    else:
        print("  [--] VS Code `code` CLI not on PATH (skipped extension check)")

    print("\nReady." if ok else "\nFix the [!!] items above.")
    return 0 if ok else 1


def cmd_list(args) -> int:
    for name in prj.list_projects():
        tags = _git("tag", "--list", f"{name}/v*", check=False).split()
        latest = sorted(tags, key=lambda t: int(t.rsplit("v", 1)[1]))[-1] if tags else "unreleased"
        print(f"{name:32s} {latest}")
    return 0


def cmd_new(args) -> int:
    name = args.name
    if not prj.NAME_RE.match(name):
        raise SystemExit("error: project names are kebab-case, e.g. desk-cable-clip")
    dest = prj.projects_dir() / name
    if dest.exists():
        raise SystemExit(f"error: {dest} already exists")
    tpl = resources.files("od") / "templates"
    (dest / "refs").mkdir(parents=True)
    (dest / "refs" / ".gitkeep").touch()
    title = name.replace("-", " ").title()
    if args.from_stl:
        src = Path(args.from_stl)
        if not src.is_file():
            raise SystemExit(f"error: {src} not found")
        shutil.copy2(src, dest / "refs" / src.name)
        design = (tpl / "remix.py.tmpl").read_text().format(name=name, stl=src.name)
    else:
        design = (tpl / "design.py.tmpl").read_text().format(name=name)
    (dest / "design.py").write_text(design)
    (dest / "README.md").write_text((tpl / "README.md.tmpl").read_text().format(title=title))
    print(f"created {dest.relative_to(prj.repo_root())}/ (design.py, README.md, refs/)")
    return 0


def cmd_check(args) -> int:
    from od.check import check_parts

    p = prj.load(args.project)
    reports = [check_parts(p, v, params) for v, params in _variants(p, args.variant).items()]
    if args.json:
        print(json.dumps({"project": p.name, "ok": all(r.ok for r in reports),
                          "variants": [r.as_dict() for r in reports]}, indent=2))
    else:
        for r in reports:
            print(f"{p.name} [{r.variant}]: {'OK' if r.ok else 'FAILED'}  (verify: {r.verify})")
            for name, info in r.parts.items():
                s = info.get("size")
                if s:
                    print(f"  {name:16s} {s[0]:8.2f} × {s[1]:8.2f} × {s[2]:8.2f} mm  "
                          f"vol {info['volume_mm3']:.0f} mm³  watertight={info['watertight']}")
            for e in r.errors:
                print(f"  ERROR: {e}")
            for w in r.warnings:
                print(f"  warn:  {w}")
    return 0 if all(r.ok for r in reports) else 1


def cmd_render(args) -> int:
    from od import render

    p = prj.load(args.project)
    out_dir = p.build_dir / "renders"
    first = next(iter(p.variants()))
    for v, params in _variants(p, args.variant).items():
        parts = p.build(params)
        stem = p.file_stem(v)
        items = render.prepare(parts)
        path = render.contact_sheet(parts, f"{p.name} [{v}]", out_dir / f"{stem}-sheet.png", items=items)
        print(path.relative_to(prj.repo_root()))
        if v == first:  # README thumbnail: kept current and committed with the design
            hero = render.hero(parts, p.path / "renders" / "hero.png", items=items)
            print(hero.relative_to(prj.repo_root()))
    return 0


def cmd_view(args) -> int:
    from od.view import show_parts, variant_parts

    p = prj.load(args.project)
    m = p.module
    show_parts(variant_parts(m.build, m.Params, getattr(m, "VARIANTS", None), args.variant))
    return 0


def cmd_watch(args) -> int:
    from od.watch import run

    return run(args.project)


def cmd_build(args) -> int:
    from od.export import export_parts

    p = prj.load(args.project)
    formats = tuple(f.strip() for f in args.formats.split(","))
    for v, params in _variants(p, args.variant).items():
        parts = p.build(params)
        for path in export_parts(parts, p.build_dir / v, p.file_stem(v), formats):
            print(path.relative_to(prj.repo_root()))
    return 0


def cmd_release(args) -> int:
    from od import render
    from od.check import check_parts
    from od.export import export_parts

    p = prj.load(args.project)
    rel = p.path.relative_to(prj.repo_root()).as_posix()

    reports = [check_parts(p, v, params) for v, params in p.variants().items()]
    failed = [r for r in reports if not r.ok]
    if failed:
        for r in failed:
            print(f"[{r.variant}] " + "\n".join(r.errors))
        raise SystemExit("error: checks failed; fix them before releasing")

    tags = _git("tag", "--list", f"{p.name}/v*", check=False).split()
    nums = [int(m.group(1)) for t in tags if (m := re.search(r"/v(\d+)$", t))]
    version = f"v{max(nums, default=0) + 1}"
    tag = f"{p.name}/{version}"

    exports = p.path / "exports"
    if exports.exists():
        shutil.rmtree(exports)
    renders = p.path / "renders"
    renders.mkdir(exist_ok=True)
    for i, (v, params) in enumerate(p.variants().items()):
        parts = p.build(params)
        stem = p.file_stem(v)
        export_parts(parts, exports, stem)
        items = render.prepare(parts)
        render.contact_sheet(parts, f"{p.name} {version} [{v}]", renders / f"{stem}-sheet.png", items=items)
        if i == 0:
            render.hero(parts, renders / "hero.png", items=items)

    branch = _git("branch", "--show-current", check=False)
    if branch not in ("main", "master"):
        print(f"note: releasing from branch '{branch}'. The tag will point at this branch's commit.")

    if args.no_git:
        print(f"exported {rel}/exports and renders (no commit/tag; would be {tag})")
        return 0
    _git("add", "--", rel)
    msg = args.message or f"release({p.name}): {version}"
    _git("commit", "-m", msg, "--", rel)
    _git("tag", "-a", tag, "-m", msg)
    print(f"committed and tagged {tag}. Push with: git push --follow-tags")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="od", description="ObjectDesign build tool (build123d → 3D printer)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="check this machine is ready").set_defaults(fn=cmd_setup)
    sub.add_parser("list", help="list projects and their latest release").set_defaults(fn=cmd_list)

    s = sub.add_parser("new", help="scaffold projects/<name>/")
    s.add_argument("name")
    s.add_argument("--from-stl", metavar="FILE", help="start a remix from an existing STL (copied to refs/)")
    s.set_defaults(fn=cmd_new)

    for name, fn, hlp in (
        ("check", cmd_check, "validate geometry, printability and verify()"),
        ("render", cmd_render, "contact sheet per variant to build/renders/ + README image renders/hero.png"),
        ("build", cmd_build, "export to projects/<name>/build/<variant>/"),
    ):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("project", help="project name or path")
        s.add_argument("--variant", help="only this variant")
        if name == "check":
            s.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "build":
            s.add_argument("--formats", default="3mf,step,stl", help="comma list of 3mf,step,stl")
        s.set_defaults(fn=fn)

    s = sub.add_parser("view", help="show a design in the OCP CAD Viewer")
    s.add_argument("project", help="project name or path")
    s.add_argument("--variant", help="variant name, or 'all' to show every variant side by side")
    s.set_defaults(fn=cmd_view)

    s = sub.add_parser("watch", help="live preview: re-send the design on save and when the viewer opens")
    s.add_argument("project", nargs="?", help="always show this project (default: last saved design)")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("release", help="export to exports/, render, commit and tag <project>/vN")
    s.add_argument("project")
    s.add_argument("-m", "--message", help="commit/tag message")
    s.add_argument("--no-git", action="store_true", help="export and render only")
    s.set_defaults(fn=cmd_release)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
