#!/usr/bin/env python3
"""Install or verify the single Verdant Mint Typora theme."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
THEME_FILES = (
    Path("verdant-mint.css"),
    Path("verdant") / "base.css",
)


def default_theme_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is unavailable; pass --theme-dir explicitly")
    return Path(appdata) / "Typora" / "themes"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(relative: Path) -> Path:
    if relative.name == "verdant-mint.css":
        return ROOT / "themes" / relative
    return ROOT / "themes" / relative


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_text = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    os.close(file_descriptor)
    temporary = Path(temporary_text)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def backup_existing(target: Path, theme_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    relative = target.relative_to(theme_dir)
    backup = theme_dir / "old-themes" / relative.parent / (
        relative.name + f".{timestamp}.bak"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)
    return backup


def install(theme_dir: Path) -> dict[str, object]:
    theme_dir = theme_dir.expanduser().resolve()
    theme_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []
    for relative in THEME_FILES:
        source = source_path(relative)
        target = theme_dir / relative
        source_hash = sha256_file(source)
        existing_hash = sha256_file(target) if target.is_file() else None
        backup = None
        changed = existing_hash != source_hash
        if changed:
            if target.is_file():
                backup = backup_existing(target, theme_dir)
            atomic_copy(source, target)
        installed_hash = sha256_file(target)
        files.append(
            {
                "relative_path": relative.as_posix(),
                "changed": changed,
                "source_sha256": source_hash,
                "installed_sha256": installed_hash,
                "backup": str(backup) if backup else None,
            }
        )
    return {
        "schema": "typora-theme-pack.install.v1",
        "action": "install",
        "theme_dir": str(theme_dir),
        "license_state_touched": False,
        "files": files,
        "verified": all(
            item["source_sha256"] == item["installed_sha256"] for item in files
        ),
    }


def verify(theme_dir: Path) -> dict[str, object]:
    theme_dir = theme_dir.expanduser().resolve()
    files: list[dict[str, object]] = []
    for relative in THEME_FILES:
        source = source_path(relative)
        target = theme_dir / relative
        source_hash = sha256_file(source)
        installed_hash = sha256_file(target) if target.is_file() else None
        files.append(
            {
                "relative_path": relative.as_posix(),
                "exists": target.is_file(),
                "source_sha256": source_hash,
                "installed_sha256": installed_hash,
                "matches": installed_hash == source_hash,
            }
        )
    return {
        "schema": "typora-theme-pack.install.v1",
        "action": "verify",
        "theme_dir": str(theme_dir),
        "license_state_touched": False,
        "files": files,
        "verified": all(item["matches"] for item in files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install or verify the Verdant Mint Typora theme without touching licensing."
    )
    parser.add_argument("action", choices=("install", "verify"))
    parser.add_argument("--theme-dir", type=Path)
    args = parser.parse_args()

    theme_dir = args.theme_dir or default_theme_dir()
    report = install(theme_dir) if args.action == "install" else verify(theme_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
