#!/usr/bin/env python3
"""Persist the machine-local converter used by editor-launched exports."""

from __future__ import annotations

import argparse
import sys

from export_pdf import LOCAL_CONFIG, save_local_converter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure the persistent converter for Typora Theme Pack exports."
    )
    parser.add_argument(
        "--converter",
        required=True,
        help="Path to a compatible Markdown-to-PDF converter script",
    )
    args = parser.parse_args()

    try:
        converter = save_local_converter(args.converter)
    except (FileNotFoundError, OSError) as error:
        print(error, file=sys.stderr)
        return 2

    print(f"Configured converter={converter} config={LOCAL_CONFIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
