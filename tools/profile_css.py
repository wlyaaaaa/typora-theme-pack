"""Load shared theme styles without preview-rendering dependencies."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
EXPORT_PROFILES = ROOT / "export-profiles"


def mint_theme_css() -> str:
    base = (THEMES / "verdant" / "base.css").read_text(encoding="utf-8")
    mint = (THEMES / "verdant-mint.css").read_text(encoding="utf-8")
    mint = re.sub(r"^\s*@import[^;]+;\s*", "", mint, count=1)
    return base + "\n\n" + mint


def profile_css(slug: str) -> str:
    profile = (EXPORT_PROFILES / f"{slug}.css").read_text(encoding="utf-8")
    if slug == "personal":
        return mint_theme_css() + "\n\n" + profile
    return profile
