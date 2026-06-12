#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "locus.plugin.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_manifest() -> dict:
    if not MANIFEST.exists():
        fail("locus.plugin.json is missing")
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        fail(f"locus.plugin.json is invalid JSON: {exc}")


def require_text(manifest: dict, key: str) -> str:
    value = str(manifest.get(key, "")).strip()
    if not value:
        fail(f"locus.plugin.json is missing {key!r}")
    return value


def validate_component_paths(manifest: dict) -> None:
    components = manifest.get("components")
    if not isinstance(components, dict):
        fail("locus.plugin.json must include a components object")

    for group in ("views", "skills", "rules"):
        items = components.get(group, [])
        if items is None:
            continue
        if not isinstance(items, list):
            fail(f"components.{group} must be a list")
        for item in items:
            if not isinstance(item, dict):
                fail(f"components.{group} entries must be objects")
            component_id = str(item.get("id", "")).strip()
            component_path = str(item.get("path", "")).strip()
            if not component_id:
                fail(f"components.{group} entry is missing id")
            if not component_path:
                fail(f"components.{group}.{component_id} is missing path")
            resolved = (ROOT / component_path).resolve()
            if ROOT not in resolved.parents and resolved != ROOT:
                fail(f"components.{group}.{component_id} path escapes repository root")
            if not resolved.exists():
                fail(f"components.{group}.{component_id} path does not exist: {component_path}")


def main() -> None:
    manifest = read_manifest()
    plugin_id = require_text(manifest, "id")
    require_text(manifest, "name")
    version = require_text(manifest, "version")
    if not SEMVER.match(version):
        fail(f"version must look like semver, got {version!r}")
    if manifest.get("schemaVersion") != 1:
        fail("schemaVersion must be 1")
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", plugin_id):
        fail("id must use lowercase letters, numbers, and hyphens")
    validate_component_paths(manifest)
    print(f"ok: {plugin_id} {version}")


if __name__ == "__main__":
    main()
