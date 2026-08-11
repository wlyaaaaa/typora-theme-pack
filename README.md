# Typora Theme Pack

一个小型、可公开复用的 Typora 视觉包：一套 Verdant Mint 编辑主题，配套三种语义化 Markdown/PDF 导出样式。

This project contains the theme and presentation profiles only. The PDF
engine is an external, user-selected converter so the pack stays independent
from any specific editor, local toolkit, or machine path.

## What is included

- `themes/verdant-mint.css`：Typora 主题菜单中的唯一新增主题。
- `themes/verdant/base.css`：主题使用的公共结构样式，不单独出现在菜单中。
- `export-profiles/original.css`：中性、忠实原文的 Markdown 样式。
- `export-profiles/personal.css`：适合个人长文阅读的薄荷样式。
- `export-profiles/company.css`：克制的专业文档样式，不添加虚构品牌或客户信息。
- `tools/install_theme.py`：安装与校验主题，保留其他用户主题。
- `tools/export_pdf.py`：把上述 CSS 交给外部 PDF 转换器，并校验源 Markdown 未被改写。
- `samples/`、`previews/`：公开演示样例。

## Requirements

- Python 3.10 or newer.
- Typora only for installing/using the editor theme.
- PDF export additionally requires a compatible external converter. The
  converter must accept the arguments used by `tools/export_pdf.py`, including
  `--input`, `--output`, `--css-file`, `--document-style-policy`,
  `--require-style`, and optional `--expected-pages`.
- Preview rendering is optional and may require Microsoft Edge, Node.js, and
  Playwright. It is not required for theme installation or the unit tests.

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Install the Typora theme

```powershell
python tools/install_theme.py install
python tools/install_theme.py verify
```

The installer copies only the two Verdant files. If an existing Verdant file
differs, it is backed up under Typora's `themes/old-themes` directory before
the atomic replacement. Restart Typora and choose `Verdant Mint` from the
Themes menu.

## Export Markdown to PDF

Set or pass the converter explicitly; no local/private converter path is
assumed:

```powershell
$env:MD_PDF_TOOLKIT_CONVERTER = '<path-to-compatible-converter.py>'
python tools/export_pdf.py --input <Markdown路径> --mode original
python tools/export_pdf.py --input <Markdown路径> --mode personal
python tools/export_pdf.py --input <Markdown路径> --mode company
```

You can also pass `--converter <path>` on each invocation. Use
`--output <PDF路径>` to choose an explicit output, or omit it to create a
source-adjacent file with one of these suffixes:

- `文档名-原版.pdf`
- `文档名-个人.pdf`
- `文档名-公司.pdf`

The exporter uses an external CSS file, defaults to ignoring inline Markdown
styles, and verifies that the source Markdown SHA-256 is unchanged.

### Typora custom commands

In `Preferences → Export`, add three Custom Commands. Replace the two
placeholders with paths on your machine and set the command to require no
output path:

```text
python "<PROJECT_ROOT>\tools\export_pdf.py" --converter "<CONVERTER>" --input "${currentPath}" --mode original
python "<PROJECT_ROOT>\tools\export_pdf.py" --converter "<CONVERTER>" --input "${currentPath}" --mode personal
python "<PROJECT_ROOT>\tools\export_pdf.py" --converter "<CONVERTER>" --input "${currentPath}" --mode company
```

## Verify

```powershell
python -m unittest discover -s tests -v
python tools/render_previews.py  # optional visual previews
```

`qa/` contains generated visual-QA intermediates and is intentionally ignored
by Git. The checked-in PDFs and PNGs are generic public samples, not private
documents.

## Scope and license

This repository contains original project code, CSS, samples, and tooling
developed for this pack. It does not bundle Typora, bypass Typora licensing,
or ship any proprietary converter/runtime. Typora is a trademark of its
respective owner.

Released under the MIT License; see [LICENSE](LICENSE).
