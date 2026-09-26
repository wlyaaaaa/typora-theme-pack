# Typora theme pack

- This repository owns one Typora editor theme plus three semantic Markdown/PDF CSS profiles: original, personal and company. The PDF engine is an external, user-selected compatible converter; do not bundle one or couple this pack to a particular machine.
- The theme installer changes only the two Verdant files. Preserve other themes, and back up differing Verdant files before replacement. Do not touch Typora licensing.
- Export keeps the source Markdown unchanged, uses an external CSS file, and ignores inline Markdown styling by default. Three modes must keep their distinct Chinese output suffixes.
- Do not fabricate company branding or customer details in the company profile. Checked-in samples and previews are generic public examples.
- Keep the converter configuration local and ignored by Git. The converter must accept the arguments used by `tools/export_pdf.py`; `tools/configure_converter.py` records its path for editor-launched exports.
- `NOTICE.md` and `LICENSE` carry real attribution and license information. The pack is independent of Typora and does not include its app, license, or a PDF engine.
- Run `python -m unittest discover -s tests -v` with an isolated task temporary directory. Theme installation and visual preview rendering are separate user-facing checks; do not install to the live Typora directory as a test.
