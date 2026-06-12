#!/usr/bin/env python3
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from validate_plugin import MANIFEST, ROOT, main as validate_plugin


DIST = ROOT / "dist"
EXCLUDED_DIRS = {".git", ".github", "dist", "node_modules", "__pycache__", ".idea", ".vscode"}
EXCLUDED_SUFFIXES = {".zip", ".pyc"}


def git_tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def main() -> None:
    validate_plugin()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    plugin_id = manifest["id"]
    version = manifest["version"]
    DIST.mkdir(exist_ok=True)
    archive = DIST / f"{plugin_id}-{version}.zip"
    if archive.exists():
        archive.unlink()

    files = [path for path in git_tracked_files() if path.exists() and should_include(path)]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(files):
            rel = path.relative_to(ROOT).as_posix()
            handle.write(path, rel)

    unpack_dir = DIST / "_check"
    if unpack_dir.exists():
        shutil.rmtree(unpack_dir)
    unpack_dir.mkdir()
    with zipfile.ZipFile(archive, "r") as handle:
        handle.extractall(unpack_dir)
    if not (unpack_dir / "locus.plugin.json").exists():
        raise SystemExit("archive validation failed: locus.plugin.json is not at zip root")
    shutil.rmtree(unpack_dir)
    print(archive)


if __name__ == "__main__":
    main()
