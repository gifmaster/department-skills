#!/usr/bin/env python3
"""Package skills into upload-ready zip files.

dist/skills/<skill-name>.zip    one skill, folder at the zip root (Claude and ChatGPT upload)
dist/packs/<dept>-skills.zip    every skill in a department
dist/department-skills-all.zip  the whole library

Zips are deterministic (fixed timestamps, sorted entries) so rebuilding without
changes does not create git noise.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def add(zf: zipfile.ZipFile, path: Path, arcname: str):
    info = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, path.read_bytes())


def zip_dirs(target: Path, dirs: list[Path], extra: list[tuple[Path, str]] = ()):
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as zf:
        for d in sorted(dirs):
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    add(zf, f, f"{d.name}/{f.relative_to(d).as_posix()}")
        for path, arc in extra:
            add(zf, path, arc)


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    all_dirs = []
    for dept in sorted((ROOT / "departments").iterdir()):
        skill_dirs = sorted(p for p in (dept / "skills").iterdir() if p.is_dir())
        for s in skill_dirs:
            zip_dirs(DIST / "skills" / f"{s.name}.zip", [s])
        zip_dirs(DIST / "packs" / f"{dept.name}-skills.zip", skill_dirs,
                 [(dept / "README.md", "README.md"), (dept / "INSTALL.md", "INSTALL.md")])
        all_dirs += skill_dirs
    zip_dirs(DIST / "department-skills-all.zip", all_dirs, [(ROOT / "CATALOG.md", "CATALOG.md")])
    print(f"Packaged {len(all_dirs)} skills into {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
