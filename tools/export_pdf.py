#!/usr/bin/env python3
"""Export Markdown with one controlled presentation profile.

The PDF engine is intentionally an external, user-selected converter. This
keeps the theme pack independent from any particular editor or local toolkit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from render_previews import profile_css


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / ".typora-theme-pack.local.json"
LOCAL_CONFIG_SCHEMA = "typora-theme-pack.local.v1"
MODES = ("original", "company", "personal")
MODE_LABELS = {
    "original": "原版",
    "company": "公司",
    "personal": "个人",
}


class ConverterConfigurationError(ValueError):
    """Raised when the persistent machine-local converter config is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def read_local_converter(config_path: Path = LOCAL_CONFIG) -> str | None:
    if not config_path.is_file():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConverterConfigurationError(
            f"Cannot read local converter config {config_path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ConverterConfigurationError(
            f"Local converter config must be a JSON object: {config_path}"
        )
    if payload.get("schema") != LOCAL_CONFIG_SCHEMA:
        raise ConverterConfigurationError(
            f"Unsupported or missing local converter config schema in {config_path}; "
            f"expected {LOCAL_CONFIG_SCHEMA}."
        )
    raw = payload.get("converter")
    if not isinstance(raw, str) or not nonblank(raw):
        raise ConverterConfigurationError(
            f"Local converter config must contain a non-empty converter path: {config_path}"
        )
    return raw.strip()


def resolve_converter(
    explicit: str | None = None,
    config_path: Path = LOCAL_CONFIG,
) -> Path:
    raw = nonblank(explicit)
    source = "--converter"
    if raw is None:
        raw = nonblank(os.environ.get("MD_PDF_TOOLKIT_CONVERTER"))
        source = "MD_PDF_TOOLKIT_CONVERTER"
    if raw is None:
        raw = read_local_converter(config_path)
        source = str(config_path)
    if not raw:
        raise FileNotFoundError(
            "No Markdown PDF converter configured. Pass --converter, set "
            "MD_PDF_TOOLKIT_CONVERTER, or run tools/configure_converter.py."
        )
    converter = Path(raw).expanduser()
    if source == str(config_path) and not converter.is_absolute():
        converter = config_path.parent / converter
    converter = converter.resolve()
    if not converter.is_file():
        raise FileNotFoundError(
            f"Markdown PDF converter from {source} was not found: {converter}"
        )
    return converter


def save_local_converter(
    converter_value: str,
    config_path: Path = LOCAL_CONFIG,
) -> Path:
    raw = nonblank(converter_value)
    if raw is None:
        raise FileNotFoundError("Converter path cannot be empty.")
    converter = Path(raw).expanduser().resolve()
    if not converter.is_file():
        raise FileNotFoundError(f"Markdown PDF converter not found: {converter}")

    payload = {
        "schema": LOCAL_CONFIG_SCHEMA,
        "converter": str(converter),
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            prefix=f"{config_path.name}.",
            dir=config_path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_path, config_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return converter


def default_output_path(source: Path, mode: str) -> Path:
    """Return the source-adjacent PDF path with the selected concise suffix."""
    return source.with_name(f"{source.stem}-{MODE_LABELS[mode]}.pdf")


def resolve_output_path(source: Path, mode: str, explicit: str | None) -> Path:
    """Treat an editor-expanded blank output placeholder as an omitted path."""
    raw = nonblank(explicit)
    return Path(raw).expanduser().resolve() if raw else default_output_path(source, mode)


def build_converter_command(
    converter: Path,
    source: Path,
    output: Path,
    css_file: Path,
    document_style_policy: str,
    expected_pages: int | None,
) -> list[str]:
    command = [
        sys.executable,
        str(converter),
        "--input",
        str(source),
        "--output",
        str(output),
        "--css-file",
        str(css_file),
        "--document-style-policy",
        document_style_policy,
        "--require-style",
    ]
    if expected_pages is not None:
        command.extend(["--expected-pages", str(expected_pages)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Markdown with original, company, or personal presentation."
    )
    parser.add_argument("--input", required=True, help="Markdown input path")
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--output", help="Optional PDF output path")
    parser.add_argument(
        "--converter",
        help="Path to a compatible Markdown-to-PDF converter script",
    )
    parser.add_argument(
        "--document-style-policy",
        choices=("ignore", "reject", "preserve"),
        default="ignore",
        help="Controlled profiles ignore inline Markdown CSS by default",
    )
    parser.add_argument("--expected-pages", type=int)
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".md":
        print(f"Markdown input not found: {source}", file=sys.stderr)
        return 2
    if args.expected_pages is not None and args.expected_pages < 1:
        print("--expected-pages must be at least 1", file=sys.stderr)
        return 2

    output = resolve_output_path(source, args.mode, args.output)
    try:
        converter = resolve_converter(args.converter)
    except (FileNotFoundError, ConverterConfigurationError) as error:
        print(error, file=sys.stderr)
        return 2

    source_hash_before = sha256_file(source)
    css = profile_css(args.mode)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".css",
        prefix=f"typora_profile_{args.mode}_",
        delete=False,
    ) as stream:
        temporary_css = Path(stream.name)
        stream.write(css)

    try:
        command = build_converter_command(
            converter,
            source,
            output,
            temporary_css,
            args.document_style_policy,
            args.expected_pages,
        )
        try:
            completed = subprocess.run(command, check=False)
        except OSError as error:
            print(f"Failed to start Markdown PDF converter: {error}", file=sys.stderr)
            return 2
    finally:
        temporary_css.unlink(missing_ok=True)

    if completed.returncode != 0:
        return completed.returncode
    source_hash_after = sha256_file(source)
    if source_hash_after != source_hash_before:
        print("Source Markdown changed during export; refusing success.", file=sys.stderr)
        return 1
    if not output.is_file() or output.stat().st_size <= 1024:
        print(f"PDF output missing or too small: {output}", file=sys.stderr)
        return 1

    print(
        f"Export profile={args.mode} source_sha256={source_hash_before} "
        f"output={output} bytes={output.stat().st_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
