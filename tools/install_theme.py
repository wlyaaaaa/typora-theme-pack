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
import subprocess
import tempfile
from urllib.parse import quote


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
        source = ROOT / "themes" / relative
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
        source = ROOT / "themes" / relative
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
    parser.add_argument("--live-output", type=Path, help="Write a small read-only installation snapshot with verify")
    parser.add_argument("--profile-data", type=Path)
    parser.add_argument("--host-python-registry", type=Path)
    parser.add_argument("--installation-root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.live_output and (args.action != "verify" or not args.profile_data or not args.host_python_registry):
        parser.error("--live-output requires verify, --profile-data and --host-python-registry")

    theme_dir = args.theme_dir or default_theme_dir()
    report = install(theme_dir) if args.action == "install" else verify(theme_dir)
    if args.live_output:
        args.live_output.parent.mkdir(parents=True, exist_ok=True)
        args.live_output.write_text(json.dumps(live_snapshot(report, args), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


def live_snapshot(report, args):
    """Existing verifier's on-demand result; never exports settings or private documents."""
    from configure_typora_menu import ENTRIES
    root = args.installation_root.resolve()
    profile = json.loads(bytes.fromhex(args.profile_data.read_text("ascii")).decode("utf-8"))
    python = json.loads(args.host_python_registry.read_text("utf-8-sig"))["executable"]
    converter = json.loads((root / ".typora-theme-pack.local.json").read_text("utf-8-sig"))["converter"]
    launcher = root / "tools/typora_export_launcher.ps1"
    ready = all(Path(p).is_file() for p in (python, converter, launcher, root / "tools/export_pdf.py"))
    menus = {row["key"]: row for row in profile["customExport"]}
    connected = [label for key, (label, mode) in ENTRIES.items() if ready and menus.get(key, {}).get("name") == label
        and profile.get(f"export.{key}", {}).get("command") == f'pwsh -NoProfile -ExecutionPolicy Bypass -File "{launcher}" -InputPath "${{currentPath}}" -Mode {mode}']
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(ROOT), *arguments], encoding="utf-8", creationflags=0x08000000 if os.name == "nt" else 0)
    tracked = [Path(p) for p in git("ls-files", "-z").split("\0") if p and (ROOT / p).is_file()]
    products = [p for p in tracked if p.parts[0] in {"exports", "previews"} and p.suffix in {".pdf", ".png"}]
    at = datetime.now(timezone.utc).isoformat()
    files = report["files"]
    return dict(v=1, at=at, scope="Current installed theme and configured menus; export was not run",
        metrics=dict(theme="Verdant Mint" if profile.get("theme") == "verdant-mint.css" else profile.get("theme"),
            theme_files=f'{sum(p["matches"] for p in files)}/2（缺 {sum(not p["exists"] for p in files)}、被改 {sum(p["exists"] and not p["matches"] for p in files)}）',
            menus=f"{len(connected)}/3", menu_list=connected,
            pdfs=sum(p.suffix == ".pdf" for p in products), previews=sum(p.suffix == ".png" for p in products),
            samples_changed=git("log", "-1", "--format=%cI", "--", "exports/*.pdf").strip()),
        size=dict(at=at, docs_chars=sum(len((ROOT/p).read_text("utf-8-sig")) for p in tracked if p.suffix == ".md"),
            code_lines=sum(len((ROOT/p).read_text("utf-8-sig").splitlines()) for p in tracked if p.suffix in {".py", ".ps1", ".css", ".js", ".gs"})),
        artifacts=[dict(at=git("log", "-1", "--format=%cI", "--", p.as_posix()).strip(), kind="pdf" if p.suffix == ".pdf" else "image",
            title=p.stem, status="completed", public="same", open=dict(source="typora.artifact."+hashlib.sha256(p.as_posix().encode()).hexdigest()[:12],
                href="https://raw.githubusercontent.com/wlyaaaaa/typora-theme-pack/main/"+quote(p.as_posix()))) for p in products])


if __name__ == "__main__":
    raise SystemExit(main())
