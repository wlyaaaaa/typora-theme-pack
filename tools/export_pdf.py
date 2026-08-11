#!/usr/bin/env python3
"""Export Markdown with one controlled presentation profile.

The PDF engine is intentionally an external, user-selected converter. This
keeps the theme pack independent from any particular editor or local toolkit.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from render_previews import profile_css


ROOT = Path(__file__).resolve().parents[1]
MODES = ("original", "company", "personal")
MODE_LABELS = {
    "original": "原版",
    "company": "公司",
    "personal": "个人",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_converter(explicit: str | None = None) -> Path:
    raw = explicit or os.environ.get("MD_PDF_TOOLKIT_CONVERTER")
    if not raw:
        raise FileNotFoundError(
            "No Markdown PDF converter configured. Pass --converter or set "
            "MD_PDF_TOOLKIT_CONVERTER to a compatible converter script."
        )
    converter = Path(raw).expanduser().resolve()
    if not converter.is_file():
        raise FileNotFoundError(
            "Markdown PDF converter not found. Pass --converter or set "
            f"MD_PDF_TOOLKIT_CONVERTER. Looked for: {converter}"
        )
    return converter


def default_output_path(source: Path, mode: str) -> Path:
    """Return the source-adjacent PDF path with the selected concise suffix."""
    return source.with_name(f"{source.stem}-{MODE_LABELS[mode]}.pdf")


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
        print(f"Markdown input not found: {source}")
        return 2
    if args.expected_pages is not None and args.expected_pages < 1:
        print("--expected-pages must be at least 1")
        return 2

    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(source, args.mode)
    )
    try:
        converter = resolve_converter(args.converter)
    except FileNotFoundError as error:
        print(error)
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
        completed = subprocess.run(command, check=False)
    finally:
        temporary_css.unlink(missing_ok=True)

    if completed.returncode != 0:
        return completed.returncode
    source_hash_after = sha256_file(source)
    if source_hash_after != source_hash_before:
        print("Source Markdown changed during export; refusing success.")
        return 1
    if not output.is_file() or output.stat().st_size <= 1024:
        print(f"PDF output missing or too small: {output}")
        return 1

    print(
        f"Export profile={args.mode} source_sha256={source_hash_before} "
        f"output={output} bytes={output.stat().st_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
