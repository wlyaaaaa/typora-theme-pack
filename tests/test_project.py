import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThemeProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previews = load_module("render_previews", TOOLS / "render_previews.py")
        cls.exporter = load_module("export_pdf", TOOLS / "export_pdf.py")
        cls.installer = load_module("install_theme", TOOLS / "install_theme.py")

    def test_package_exposes_exactly_one_typora_app_theme(self):
        root_themes = sorted(path.name for path in (ROOT / "themes").glob("*.css"))

        self.assertEqual(root_themes, ["verdant-mint.css"])
        self.assertTrue((ROOT / "themes" / "verdant" / "base.css").is_file())

    def test_export_profile_meanings_are_separate(self):
        original = self.previews.profile_css("original")
        company = self.previews.profile_css("company")
        personal = self.previews.profile_css("personal")

        self.assertIn("--ink: #24292f", original)
        self.assertNotIn("#07854b", original)
        self.assertIn('"HarmonyOS Sans SC"', original)
        self.assertIn("--brand: #243b53", company)
        self.assertNotIn("#07854b", company)
        self.assertNotIn("#078d50", company)
        self.assertNotIn("#f7faf8", company)
        self.assertIn("border-bottom: 0", company)
        for forbidden in ("CORPORATE DOCUMENT", "client", "客户", "fake brand"):
            self.assertNotIn(forbidden.casefold(), company.casefold())
        self.assertIn("#07854b", personal)
        self.assertIn("#078d50", personal)

    def test_exporter_passes_profile_css_without_rewriting_markdown(self):
        command = self.exporter.build_converter_command(
            Path("converter.py"),
            Path("source.md"),
            Path("output.pdf"),
            Path("profile.css"),
            "ignore",
            2,
        )

        self.assertIn("--css-file", command)
        self.assertIn("profile.css", command)
        self.assertIn("--document-style-policy", command)
        self.assertIn("ignore", command)
        self.assertIn("--expected-pages", command)

    def test_exporter_requires_an_explicit_external_converter(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing_config = Path(temporary) / "missing.json"
            with patch.dict(os.environ, {"MD_PDF_TOOLKIT_CONVERTER": ""}, clear=True):
                with self.assertRaisesRegex(
                    FileNotFoundError, "No Markdown PDF converter configured"
                ):
                    self.exporter.resolve_converter(config_path=missing_config)

    def test_exporter_uses_persistent_machine_local_converter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            converter = root / "converter.py"
            converter.write_text("# compatible test converter\n", encoding="utf-8")
            config = root / ".typora-theme-pack.local.json"
            config.write_text(
                json.dumps(
                    {
                        "schema": self.exporter.LOCAL_CONFIG_SCHEMA,
                        "converter": str(converter),
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"MD_PDF_TOOLKIT_CONVERTER": ""}, clear=True):
                self.assertEqual(
                    self.exporter.resolve_converter(config_path=config),
                    converter.resolve(),
                )

    def test_converter_configuration_is_atomic_and_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            converter = root / "converter.py"
            converter.write_text("# compatible test converter\n", encoding="utf-8")
            config = root / ".typora-theme-pack.local.json"

            saved = self.exporter.save_local_converter(str(converter), config)
            payload = json.loads(config.read_text(encoding="utf-8"))

            self.assertEqual(saved, converter.resolve())
            self.assertEqual(payload["schema"], self.exporter.LOCAL_CONFIG_SCHEMA)
            self.assertEqual(Path(payload["converter"]), converter.resolve())
            self.assertEqual(list(root.glob(f"{config.name}.*.tmp")), [])

    def test_blank_typora_output_placeholder_uses_default_filename(self):
        source = Path("项目说明.md")

        self.assertEqual(
            self.exporter.resolve_output_path(source, "personal", ""),
            Path("项目说明-个人.pdf"),
        )
        self.assertEqual(
            self.exporter.resolve_output_path(source, "company", "   "),
            Path("项目说明-公司.pdf"),
        )

    def test_public_docs_do_not_contain_machine_specific_paths(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"[A-Za-z]:\\", readme))
        self.assertNotIn(".agents", readme)

    def test_default_pdf_filenames_use_concise_chinese_suffixes(self):
        source = Path("项目说明.md")

        self.assertEqual(
            self.exporter.default_output_path(source, "original"),
            Path("项目说明-原版.pdf"),
        )
        self.assertEqual(
            self.exporter.default_output_path(source, "personal"),
            Path("项目说明-个人.pdf"),
        )
        self.assertEqual(
            self.exporter.default_output_path(source, "company"),
            Path("项目说明-公司.pdf"),
        )

    def test_typora_code_fence_lines_do_not_inherit_block_cards(self):
        css = (ROOT / "themes" / "verdant" / "base.css").read_text(encoding="utf-8")

        self.assertIn("#write .md-fences .CodeMirror pre", css)
        self.assertIn("#write .md-fences pre.CodeMirror-line", css)
        reset = css.split("#write .md-fences .CodeMirror pre", 1)[1].split("}", 1)[0]
        self.assertIn("border-radius: 0", reset)
        self.assertIn("background: transparent", reset)
        self.assertIn("box-shadow: none", reset)

    def test_installer_preserves_unrelated_themes_and_verifies_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme_dir = Path(temporary) / "themes"
            theme_dir.mkdir(parents=True)
            unrelated = theme_dir / "unrelated.css"
            unrelated.write_text("body { color: red; }\n", encoding="utf-8")

            installed = self.installer.install(theme_dir)
            verified = self.installer.verify(theme_dir)

            self.assertTrue(installed["verified"])
            self.assertTrue(verified["verified"])
            self.assertTrue(unrelated.is_file())
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "body { color: red; }\n")
            self.assertTrue((theme_dir / "verdant-mint.css").is_file())
            self.assertTrue((theme_dir / "verdant" / "base.css").is_file())


if __name__ == "__main__":
    unittest.main()
