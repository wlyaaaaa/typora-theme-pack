#!/usr/bin/env python3
"""Render Typora-compatible theme previews without controlling desktop apps."""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
EXPORT_PROFILES = ROOT / "export-profiles"
SAMPLE = ROOT / "samples" / "00-主题预览.md"
HTML_DIR = ROOT / "qa" / "html"
STYLED_MD_DIR = ROOT / "qa" / "styled-md"
SOFTWARE_DIR = ROOT / "previews" / "software"
MARKDOWN_DIR = ROOT / "previews" / "markdown"
PLAYWRIGHT_HELPER = ROOT / "tools" / "render_html_png_playwright.js"

EDGE_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)

THEME_META = {
    "original": {
        "cn": "原样",
        "app_cn": "薄荷",
        "en": "MARKDOWN STANDARD",
        "tag": "中性、朴素、忠实原文",
        "swatch": "#57606a",
    },
    "company": {
        "cn": "公司内部",
        "en": "TEAM DOCUMENT",
        "tag": "公司内部、专业审阅",
        "swatch": "#243b53",
    },
    "personal": {
        "cn": "自己阅读",
        "en": "PERSONAL READING",
        "tag": "更大字号、舒展长读",
        "swatch": "#078d50",
    },
}


def edge_path() -> Path:
    for candidate in EDGE_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Microsoft Edge not found")


def playwright_runtime() -> tuple[Path, Path] | None:
    node_candidates = []
    if os.environ.get("MD_PDF_PLAYWRIGHT_NODE"):
        node_candidates.append(Path(os.environ["MD_PDF_PLAYWRIGHT_NODE"]))
    if shutil.which("node"):
        node_candidates.append(Path(shutil.which("node")))
    node_candidates.append(
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )

    module_candidates = []
    if os.environ.get("MD_PDF_PLAYWRIGHT_MODULES"):
        module_candidates.extend(
            Path(value)
            for value in os.environ["MD_PDF_PLAYWRIGHT_MODULES"].split(os.pathsep)
            if value
        )
    if os.environ.get("NODE_PATH"):
        module_candidates.extend(
            Path(value) for value in os.environ["NODE_PATH"].split(os.pathsep) if value
        )
    module_candidates.append(
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "node_modules"
    )

    nodes = [path.resolve() for path in node_candidates if path.is_file()]
    modules = [
        path.resolve()
        for path in module_candidates
        if (path / "playwright" / "package.json").is_file()
    ]
    if nodes and modules and PLAYWRIGHT_HELPER.is_file():
        return nodes[0], modules[0]
    return None


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


def markdown_html() -> str:
    return markdown.markdown(
        SAMPLE.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
    )


def app_html(slug: str, css: str, article: str) -> str:
    meta = THEME_META[slug]
    app_cn = meta.get("app_cn", meta["cn"])
    preview_css = r"""
      * { box-sizing: border-box; }
      html, body { width: 1500px; height: 1000px; margin: 0; overflow: hidden; }
      body { padding: 26px; background: #d9e2de !important; }
      .app-shell {
        width: 1448px; height: 948px; overflow: hidden;
        border: 1px solid rgba(15,55,42,.16); border-radius: 18px;
        background: var(--canvas); box-shadow: 0 26px 70px rgba(15,45,36,.24);
      }
      .app-topbar {
        height: 50px; display: flex; align-items: center; gap: 14px;
        padding: 0 18px; background: var(--titlebar-bg); color: var(--titlebar-ink);
        font-family: var(--font-body); user-select: none;
      }
      .brand-mark {
        width: 28px; height: 28px; display: grid; place-items: center;
        border: 1px solid rgba(255,255,255,.55); border-radius: 8px;
        background: rgba(255,255,255,.13); font-family: Georgia, serif;
        font-size: 18px; font-weight: 700;
      }
      .app-title { font-size: 13px; font-weight: 650; letter-spacing: .02em; }
      .app-title span { opacity: .62; font-weight: 400; }
      .app-preview-badge {
        margin-left: auto; padding: 5px 9px; border: 1px solid rgba(255,255,255,.35);
        border-radius: 999px; background: rgba(255,255,255,.11);
        font-size: 10px; letter-spacing: .05em;
      }
      .window-actions { display: flex; gap: 18px; opacity: .78; font-size: 13px; }
      .app-body { display: flex; height: 898px; }
      #typora-sidebar {
        position: relative !important; inset: auto !important; display: flex !important;
        flex-direction: column; width: 252px !important; height: 898px;
        padding: 26px 18px 18px; overflow: hidden; contain: none;
      }
      .sidebar-eyebrow { margin: 0 10px 18px; opacity: .62; font-size: 10px; font-weight: 800; letter-spacing: .16em; }
      .sidebar-tabs-preview { display: flex; gap: 8px; margin: 0 6px 19px; }
      .sidebar-tab-preview {
        flex: 1; padding: 8px 9px; border-radius: 8px; background: rgba(255,255,255,.18);
        font-size: 12px; text-align: center;
      }
      .sidebar-tab-preview.active { background: var(--active-file-bg-color); color: var(--active-file-text-color); font-weight: 700; }
      .file-group { margin: 8px 8px 7px; opacity: .62; font-size: 10px; font-weight: 750; letter-spacing: .12em; }
      .file-node-content {
        display: flex; align-items: center; gap: 10px; min-height: 39px;
        margin: 2px 0; padding: 8px 10px; border-radius: 8px; font-size: 13px;
      }
      .file-node-content.active { background: var(--active-file-bg-color); color: var(--active-file-text-color); font-weight: 700; }
      .file-icon { width: 19px; height: 23px; display: grid; place-items: center; border: 1px solid currentColor; border-radius: 4px; opacity: .76; font-size: 8px; }
      .sidebar-bottom { margin-top: auto; padding: 15px 10px 0; border-top: 1px solid rgba(127,154,143,.22); opacity: .66; font-size: 11px; }
      .editor-pane { position: relative; flex: 1; height: 898px; overflow: hidden; background: var(--canvas); }
      .editor-toolbar {
        position: absolute; z-index: 3; left: 0; right: 0; top: 0; height: 44px;
        display: flex; align-items: center; gap: 9px; padding: 0 25px;
        border-bottom: 1px solid var(--line); background: color-mix(in srgb, var(--paper) 92%, var(--surface));
        color: var(--ink-soft); font-size: 12px;
      }
      .toolbar-pill { padding: 5px 10px; border: 1px solid var(--line); border-radius: 7px; background: var(--paper); }
      .toolbar-status { margin-left: auto; color: var(--brand); font-weight: 700; }
      content {
        display: block; position: absolute; inset: 44px 0 0; height: auto; overflow: hidden;
        background: var(--canvas) !important;
      }
      #write {
        width: calc(100% - 82px); max-width: 850px; min-height: 1120px;
        margin: 28px auto 80px; padding: 52px 64px 95px;
        font-size: 14.2px; line-height: 1.72;
      }
      #write h1 { font-size: 2.05em; margin-bottom: .66em; }
      #write > h1:first-child + p { margin-bottom: 1.45em; }
      #write h2 { margin-top: 1.42em; font-size: 1.35em; }
      #write h3 { margin-top: 1.25em; }
      #write blockquote { margin: 1em 0; padding-top: .75em; padding-bottom: .75em; }
      #write table { font-size: .82em; margin-top: .8em; }
      #write pre { font-size: .76em; }
    """
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style><style>{preview_css}</style></head>
<body><div class="app-shell">
  <div class="app-topbar"><div class="brand-mark">T</div><div class="app-title">{app_cn} · Typora <span>/ 00-主题预览.md</span></div><div class="app-preview-badge">浏览器概念预览</div><div class="window-actions"><span>—</span><span>□</span><span>×</span></div></div>
  <div class="app-body">
    <aside id="typora-sidebar">
      <div class="sidebar-eyebrow">VERDANT WORKSPACE</div>
      <div class="sidebar-tabs-preview"><div class="sidebar-tab-preview active">文件</div><div class="sidebar-tab-preview">大纲</div></div>
      <div class="file-group">主题样张</div>
      <div class="file-node-content active"><span class="file-icon">MD</span>00-主题预览</div>
      <div class="file-node-content"><span class="file-icon">MD</span>01-项目简报</div>
      <div class="file-node-content"><span class="file-icon">MD</span>02-长文笔记</div>
      <div class="file-node-content"><span class="file-icon">MD</span>03-数据摘要</div>
      <div class="file-group">主题</div>
      <div class="file-node-content"><span class="file-icon">CSS</span>{app_cn} · Mint Emerald</div>
      <div class="sidebar-bottom">{meta['tag']}<br>UTF-8 · Markdown</div>
    </aside>
    <section class="editor-pane"><div class="editor-toolbar"><span class="toolbar-pill">H1</span><span class="toolbar-pill">B</span><span class="toolbar-pill">引用</span><span class="toolbar-pill">表格</span><span class="toolbar-status">● 已保存</span></div><content><article id="write">{article}</article></content></section>
  </div>
</div></body></html>"""


def code_fence_regression_html(css: str) -> str:
    """Render the Typora 1.14 CodeMirror line structure that caused the bug."""
    code_lines = (
        "<pre class='CodeMirror-line'><span>{</span></pre>",
        "<pre class='CodeMirror-line'><span>  <span class='cm-property'>&quot;theme&quot;</span>: <span class='cm-string'>&quot;verdant&quot;</span>,</span></pre>",
        "<pre class='CodeMirror-line'><span>  <span class='cm-property'>&quot;purpose&quot;</span>: <span class='cm-string'>&quot;read-edit-export&quot;</span>,</span></pre>",
        "<pre class='CodeMirror-line'><span>  <span class='cm-property'>&quot;primaryColor&quot;</span>: <span class='cm-string'>&quot;green&quot;</span>,</span></pre>",
        "<pre class='CodeMirror-line'><span>  <span class='cm-property'>&quot;printReady&quot;</span>: <span class='cm-atom'>true</span></span></pre>",
        "<pre class='CodeMirror-line'><span>}</span></pre>",
    )
    lines = "".join(code_lines)
    preview_css = r"""
      * { box-sizing: border-box; }
      html, body { width: 1240px; height: 920px; margin: 0; overflow: hidden; }
      body { padding: 48px; background: var(--canvas) !important; }
      .preview-label {
        margin: 0 auto 18px; max-width: 1060px; color: var(--ink-soft);
        font-family: var(--font-body); font-size: 13px; letter-spacing: .025em;
      }
      #write {
        width: 1060px; max-width: none; min-height: 780px; margin: 0 auto;
        padding: 58px 70px 72px; font-size: 17px; line-height: 1.78;
      }
      #write h2 { margin-top: 0; }
      .CodeMirror { height: auto; position: relative; overflow: hidden; }
      .CodeMirror-scroll { height: auto; overflow: visible; position: relative; }
      .CodeMirror-lines { padding: 0; }
      .CodeMirror-code { position: relative; }
      .CodeMirror pre { position: relative; overflow: visible; }
      .cm-property { color: #173f31; }
      .cm-string { color: #b4232b; }
      .cm-atom { color: #2c2a9b; }
    """
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style><style>{preview_css}</style></head>
<body><div class="preview-label">浏览器回归预览 · Typora 1.14 CodeMirror DOM</div>
<article id="write">
  <h2>03 / 示例内容</h2>
  <p>修复后，整段代码只保留一个容器；每一行不再继承圆角卡片和绿色竖线。</p>
  <div class="md-fences"><div class="CodeMirror cm-s-inner"><div class="CodeMirror-scroll"><div class="CodeMirror-lines"><div class="CodeMirror-code">{lines}</div></div></div></div></div>
  <blockquote><p><strong>结论：</strong>代码仍然有语法高亮，但视觉结构恢复为一个完整代码块。</p></blockquote>
</article></body></html>"""


def document_html(slug: str, css: str, article: str) -> str:
    meta = THEME_META[slug]
    preview_css = r"""
      * { box-sizing: border-box; }
      html, body { width: 1240px; height: 1680px; margin: 0; overflow: hidden; }
      body { padding: 50px 52px; background: var(--canvas) !important; }
      .preview-label {
        position: fixed; z-index: 5; right: 66px; top: 67px; padding: 8px 13px;
        border-radius: 999px; background: var(--brand); color: white;
        font-family: var(--font-body); font-size: 11px; font-weight: 750; letter-spacing: .08em;
        box-shadow: 0 5px 18px rgba(10,70,50,.18);
      }
      #write {
        width: 1136px; max-width: none; min-height: 1580px; margin: 0;
        padding: 76px 86px 105px; border-radius: var(--radius); font-size: 16px; line-height: 1.82;
      }
      #write h1 { font-size: 2.35em; }
      #write h2 { margin-top: 1.85em; }
      #write table { font-size: .88em; }
    """
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style><style>{preview_css}</style></head><body><div class="preview-label">浏览器渲染 · {meta['cn']}</div><article id="write">{article}</article></body></html>"""


def render_png(edge: Path, source: Path, output: Path, width: int, height: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = playwright_runtime()
    if runtime is not None:
        node, modules = runtime
        environment = os.environ.copy()
        environment["NODE_PATH"] = str(modules)
        completed = subprocess.run(
            [
                str(node),
                str(PLAYWRIGHT_HELPER),
                str(edge),
                str(source),
                str(output),
                str(width),
                str(height),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=environment,
        )
        if completed.returncode == 0 and output.is_file() and output.stat().st_size >= 1024:
            return
        output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="verdant_edge_") as profile:
        command = [
            str(edge),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--allow-file-access-from-files",
            "--force-device-scale-factor=1",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1200",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--screenshot={output}",
            source.as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if completed.returncode != 0 or not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError(f"Edge screenshot failed for {source.name}: {completed.stderr}")


def export_css(css: str) -> str:
    """Adapt Typora's #write-scoped document rules to the PDF converter body."""
    adapted = css.replace("#write", "body")
    adapted += "\n@media print { body { width:auto !important; max-width:none !important; min-height:0 !important; margin:0 !important; padding:0 !important; border:0 !important; box-shadow:none !important; } }\n"
    return adapted


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\HarmonyOS_Sans_SC_Bold.ttf") if bold else Path(r"C:\Windows\Fonts\HarmonyOS_Sans_SC_Regular.ttf"),
        Path(r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf") if bold else Path(r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def contact_sheet(kind: str, source_dir: Path, output: Path, thumb_size: tuple[int, int]) -> None:
    width = 2070
    header = 118
    gap = 30
    card_w = (width - gap * 4) // 3
    card_h = thumb_size[1] + 96
    height = header + card_h + gap * 2
    sheet = Image.new("RGB", (width, height), "#eef3f0")
    draw = ImageDraw.Draw(sheet)
    draw.text((52, 32), "软件概念预览" if kind == "software" else "Markdown / PDF 页面预览", fill="#163d31", font=font(38, True))
    draw.text((52, 78), "三种语义 · 忠实原样 / 公司内部 / 个人阅读", fill="#668078", font=font(19))

    for index, (slug, meta) in enumerate(THEME_META.items()):
        row, col = divmod(index, 3)
        x = gap + col * (card_w + gap)
        y = header + gap + row * (card_h + gap)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=22, fill="#ffffff", outline="#d3e1db", width=2)
        image = Image.open(source_dir / f"{slug}.png").convert("RGB")
        image.thumbnail(thumb_size, Image.Resampling.LANCZOS)
        ix = x + (card_w - image.width) // 2
        iy = y + 22
        sheet.paste(image, (ix, iy))
        label_y = y + thumb_size[1] + 35
        draw.ellipse((x + 26, label_y + 4, x + 42, label_y + 20), fill=meta["swatch"])
        draw.text((x + 54, label_y), f"{meta['cn']}  {meta['en']}", fill="#193a30", font=font(22, True))
        draw.text((x + 54, label_y + 31), meta["tag"], fill="#6c817a", font=font(16))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=94)


def main() -> None:
    edge = edge_path()
    for directory in (HTML_DIR, STYLED_MD_DIR, SOFTWARE_DIR, MARKDOWN_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    article = markdown_html()
    sample_source = SAMPLE.read_text(encoding="utf-8")

    original_css = mint_theme_css()
    app_path = HTML_DIR / "verdant-mint-software.html"
    app_path.write_text(app_html("original", original_css, article), encoding="utf-8")
    software_path = SOFTWARE_DIR / "verdant-mint.png"
    render_png(edge, app_path, software_path, 1500, 1000)
    shutil.copy2(software_path, ROOT / "previews" / "software-overview.png")

    regression_path = HTML_DIR / "typora-code-fence-regression.html"
    regression_path.write_text(
        code_fence_regression_html(original_css),
        encoding="utf-8",
    )
    render_png(
        edge,
        regression_path,
        ROOT / "previews" / "typora-code-block-fixed.png",
        1240,
        920,
    )

    for slug in THEME_META:
        css = profile_css(slug)
        doc_path = HTML_DIR / f"{slug}-markdown.html"
        doc_path.write_text(document_html(slug, css, article), encoding="utf-8")
        render_png(edge, doc_path, MARKDOWN_DIR / f"{slug}.png", 1240, 1680)

        styled = f"<style>\n{export_css(css)}\n</style>\n\n{sample_source}"
        (STYLED_MD_DIR / f"{slug}.md").write_text(styled, encoding="utf-8")

    contact_sheet("markdown", MARKDOWN_DIR, ROOT / "previews" / "markdown-overview.png", (520, 704))
    print(
        "Rendered one Mint software preview, one Typora code-fence regression "
        f"preview, and {len(THEME_META)} PDF profile previews with {edge}"
    )


if __name__ == "__main__":
    main()
