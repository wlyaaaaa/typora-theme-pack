"""Refresh only this pack's three Typora export menu entries."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENTRIES = {"custom": ("原版", "original"), "custom1": ("公司", "company"), "custom2": ("个人", "personal")}


def configure(profile_path: Path, launcher: Path | None = None) -> bool:
    launcher = (launcher or ROOT / "tools" / "typora_export_launcher.ps1").resolve()
    if not launcher.is_file():
        raise FileNotFoundError(f"Typora exporter launcher missing: {launcher}")
    original = profile_path.read_bytes()
    try:
        profile = json.loads(bytes.fromhex(original.decode("ascii")).decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise ValueError("Typora profile.data is not hex-encoded JSON") from error
    if not isinstance(profile, dict) or not isinstance(profile.get("customExport"), list):
        raise ValueError("Typora export menu structure is missing")
    menu = {entry.get("key"): entry for entry in profile["customExport"] if isinstance(entry, dict)}
    for key, (label, mode) in ENTRIES.items():
        if key not in menu or not isinstance(profile.get(f"export.{key}"), dict):
            raise ValueError(f"Typora export slot missing: {key}")
        menu[key]["name"] = label
        command = f'pwsh -NoProfile -ExecutionPolicy Bypass -File "{launcher}" -InputPath "${{currentPath}}" -Mode {mode}'
        profile[f"export.{key}"]["command"] = command
    updated = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).encode("utf-8").hex().encode("ascii")
    if updated == original:
        return False
    backup = profile_path.with_name(profile_path.name + "." + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".bak")
    shutil.copy2(profile_path, backup)
    with tempfile.NamedTemporaryFile(dir=profile_path.parent, prefix=".profile.data.", suffix=".tmp", delete=False) as stream:
        staged = Path(stream.name)
        stream.write(updated)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(staged, profile_path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-data", type=Path, default=Path(os.environ["APPDATA"]) / "Typora" / "profile.data")
    args = parser.parse_args()
    print("Typora export menu updated" if configure(args.profile_data) else "Typora export menu already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
