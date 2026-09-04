#!/usr/bin/env python3
"""Assemble the static, serverless build.

Produces a directory that can be served by GitHub Pages — or any static host,
or a USB stick — and that runs the entire platform in the visitor's browser
through Pyodide. There is no backend, so there is nothing to pay for and
nothing that could log what people paste.

    python scripts/build_pages.py --out site
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "wia"
WEB = PACKAGE / "web"

#: Shipped to the browser. The API layer is excluded on purpose: FastAPI and
#: pydantic are not pure-Python-stdlib, and the browser build talks to
#: ``wia.service`` directly instead.
EXCLUDE_DIRS = {"api", "__pycache__", "web"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

SCRIPT_TAG = '<script src="boot.js"></script>\n'


def package_files() -> list[Path]:
    out: list[Path] = []
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PACKAGE)
        if set(relative.parts) & EXCLUDE_DIRS:
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        out.append(path)
    return out


def build(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # 1. The engine, as a zip Pyodide unpacks straight into its filesystem.
    archive = out_dir / "wia-package.zip"
    files = package_files()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, Path("wia") / path.relative_to(PACKAGE))

    # 2. The page, with the browser runtime injected ahead of its own script.
    html = (WEB / "index.html").read_text(encoding="utf-8")
    if SCRIPT_TAG not in html:
        html = html.replace("</head>", SCRIPT_TAG + "</head>", 1)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(WEB / "boot.js", out_dir / "boot.js")

    # 3. Pages serves this verbatim rather than running it through Jekyll.
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    size = archive.stat().st_size
    print(f"{out_dir}/")
    print(f"  wia-package.zip  {len(files):3d} files, {size / 1024:.0f} KB")
    print(f"  index.html       {(out_dir / 'index.html').stat().st_size / 1024:.0f} KB")
    print(f"  boot.js          {(out_dir / 'boot.js').stat().st_size / 1024:.0f} KB")
    print("\nServe it with any static file server, e.g.:")
    print(f"  python -m http.server -d {out_dir} 8000")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="site", help="output directory")
    args = parser.parse_args()
    build(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
