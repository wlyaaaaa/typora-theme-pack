import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_single_page_pdf(path: Path, width: int = 72, height: int = 72) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    with path.open("wb") as stream:
        writer.write(stream)
    return path.read_bytes()


class ThemeProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previews = load_module("render_previews", TOOLS / "render_previews.py")
        cls.exporter = load_module("export_pdf", TOOLS / "export_pdf.py")
        cls.installer = load_module("install_theme", TOOLS / "install_theme.py")
        cls.menu = load_module("configure_typora_menu", TOOLS / "configure_typora_menu.py")

    def test_menu_refresh_uses_registered_python_launcher_and_keeps_other_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / "profile.data"
            profile = {
                "theme": "other-theme.css",
                "customExport": [
                    {"key": key, "name": "old", "type": "custom"}
                    for key in ("custom", "custom1", "custom2")
                ],
                **{f"export.{key}": {"command": "old", "showOutput": False}
                   for key in ("custom", "custom1", "custom2")},
            }
            profile_path.write_text(json.dumps(profile).encode("utf-8").hex(), encoding="ascii")
            self.assertTrue(self.menu.configure(profile_path))
            updated = json.loads(bytes.fromhex(profile_path.read_text(encoding="ascii")).decode("utf-8"))
            self.assertEqual(updated["theme"], "other-theme.css")
            self.assertEqual([item["name"] for item in updated["customExport"]], ["原版", "公司", "个人"])
            for key, (_, mode) in self.menu.ENTRIES.items():
                command = updated[f"export.{key}"]["command"]
                self.assertIn("typora_export_launcher.ps1", command)
                self.assertIn(f"-Mode {mode}", command)
                self.assertNotIn("outputPath", command)
                self.assertFalse(updated[f"export.{key}"]["showOutput"])
            self.assertEqual(len(list(profile_path.parent.glob("profile.data.*.bak"))), 1)
            self.assertFalse(self.menu.configure(profile_path))

    def assert_no_staged_outputs(self, root: Path):
        self.assertEqual(
            list(root.glob(f"{self.exporter.STAGED_OUTPUT_PREFIX}*{self.exporter.STAGED_OUTPUT_SUFFIX}")),
            [],
        )

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

    def test_noop_converter_cannot_reuse_stale_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "noop_converter.py"
            converter.write_text("raise SystemExit(0)\n", encoding="utf-8")

            argv = [
                "export_pdf.py",
                "--input",
                str(source),
                "--mode",
                "original",
                "--output",
                str(output),
                "--converter",
                str(converter),
            ]
            with patch.object(sys, "argv", argv), patch("builtins.print"):
                result = self.exporter.main()

            self.assertEqual(result, 1)
            self.assertEqual(output.read_bytes(), old_pdf)
            self.assert_no_staged_outputs(root)

    def test_failed_converter_preserves_existing_pdf_and_removes_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "failed_converter.py"
            converter.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.write_bytes(b'%PDF-1.7\\n' + b'failed' * 400 + b'\\n%%EOF\\n')\n"
                "raise SystemExit(7)\n",
                encoding="utf-8",
            )

            argv = [
                "export_pdf.py",
                "--input",
                str(source),
                "--mode",
                "original",
                "--output",
                str(output),
                "--converter",
                str(converter),
            ]
            with patch.object(sys, "argv", argv), patch("builtins.print"):
                result = self.exporter.main()

            self.assertEqual(result, 7)
            self.assertEqual(output.read_bytes(), old_pdf)
            self.assert_no_staged_outputs(root)

    def test_pdf_shaped_junk_cannot_replace_existing_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "junk_converter.py"
            converter.write_text(
                "from pathlib import Path\nimport sys\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.write_bytes(b'%PDF-1.7\\n' + b'junk' * 400 + b'\\n%%EOF\\n')\n",
                encoding="utf-8",
            )
            argv = ["export_pdf.py", "--input", str(source), "--mode", "original", "--output", str(output), "--converter", str(converter)]
            with patch.object(sys, "argv", argv), patch("builtins.print"):
                result = self.exporter.main()
            self.assertEqual(result, 1)
            self.assertEqual(output.read_bytes(), old_pdf)
            self.assert_no_staged_outputs(root)

    def test_zero_page_pdf_cannot_replace_existing_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "zero_page_converter.py"
            converter.write_text(
                "from pathlib import Path\nimport sys\nfrom pypdf import PdfWriter\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "writer = PdfWriter()\nwith output.open('wb') as stream: writer.write(stream)\n",
                encoding="utf-8",
            )
            argv = ["export_pdf.py", "--input", str(source), "--mode", "original", "--output", str(output), "--converter", str(converter)]
            with patch.object(sys, "argv", argv), patch("builtins.print"):
                result = self.exporter.main()
            self.assertEqual(result, 1)
            self.assertEqual(output.read_bytes(), old_pdf)
            self.assert_no_staged_outputs(root)

    def test_successful_converter_atomically_replaces_pdf_without_residue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "successful_converter.py"
            converter.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "from pypdf import PdfWriter\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "writer = PdfWriter()\n"
                "writer.add_blank_page(width=144, height=144)\n"
                "with output.open('wb') as stream: writer.write(stream)\n",
                encoding="utf-8",
            )

            argv = [
                "export_pdf.py",
                "--input",
                str(source),
                "--mode",
                "original",
                "--output",
                str(output),
                "--converter",
                str(converter),
            ]
            with patch.object(sys, "argv", argv), patch("builtins.print"):
                result = self.exporter.main()

            self.assertEqual(result, 0)
            self.assertNotEqual(output.read_bytes(), old_pdf)
            reader = PdfReader(output)
            self.assertEqual(len(reader.pages), 1)
            self.assertEqual(float(reader.pages[0].mediabox.width), 144.0)
            self.assertEqual(source.read_text(encoding="utf-8"), "# Current source\n")
            self.assert_no_staged_outputs(root)

    def test_staged_output_uses_short_name_for_long_output_basename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / (("x" * 240) + ".pdf")
            staged = self.exporter.reserve_staged_output_path(output)
            self.assertEqual(staged.parent, root)
            self.assertTrue(staged.name.startswith(self.exporter.STAGED_OUTPUT_PREFIX))
            self.assertTrue(staged.name.endswith(self.exporter.STAGED_OUTPUT_SUFFIX))
            self.assertLess(len(staged.name), 255)
            self.assertFalse(staged.exists())
            self.assert_no_staged_outputs(root)

    def test_cleanup_failure_does_not_mask_converter_returncode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.pdf"
            old_pdf = write_single_page_pdf(output)
            converter = root / "failed_converter.py"
            converter.write_text(
                "from pathlib import Path\nimport sys\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.write_bytes(b'partial output')\nraise SystemExit(7)\n",
                encoding="utf-8",
            )
            argv = ["export_pdf.py", "--input", str(source), "--mode", "original", "--output", str(output), "--converter", str(converter)]
            original_unlink = Path.unlink
            def unlink_with_stage_failure(path, missing_ok=False):
                if path.name.startswith(self.exporter.STAGED_OUTPUT_PREFIX) and path.name.endswith(self.exporter.STAGED_OUTPUT_SUFFIX):
                    raise OSError("simulated staged cleanup failure")
                return original_unlink(path, missing_ok=missing_ok)
            with patch.object(Path, "unlink", new=unlink_with_stage_failure), patch.object(sys, "argv", argv), patch("sys.stderr", new_callable=io.StringIO) as stderr:
                result = self.exporter.main()
            self.assertEqual(result, 7)
            self.assertEqual(output.read_bytes(), old_pdf)
            self.assertIn("Warning: cannot remove temporary file", stderr.getvalue())

    def test_exporter_rejects_non_pdf_output_before_converter_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            output = root / "output.txt"
            converter = root / "converter.py"
            converter.write_text("raise SystemExit(0)\n", encoding="utf-8")
            argv = ["export_pdf.py", "--input", str(source), "--mode", "original", "--output", str(output), "--converter", str(converter)]
            with patch.object(sys, "argv", argv), patch.object(self.exporter.subprocess, "run") as run, patch("builtins.print"):
                result = self.exporter.main()
            self.assertEqual(result, 2)
            run.assert_not_called()

    def test_exporter_rejects_output_that_replaces_converter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.md"
            source.write_text("# Current source\n", encoding="utf-8")
            converter = root / "converter.pdf"
            converter.write_text("raise SystemExit(0)\n", encoding="utf-8")
            original_converter = converter.read_bytes()
            argv = ["export_pdf.py", "--input", str(source), "--mode", "original", "--output", str(converter), "--converter", str(converter)]
            with patch.object(sys, "argv", argv), patch.object(self.exporter.subprocess, "run") as run, patch("builtins.print"):
                result = self.exporter.main()
            self.assertEqual(result, 2)
            self.assertEqual(converter.read_bytes(), original_converter)
            run.assert_not_called()

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
