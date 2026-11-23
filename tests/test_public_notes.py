"""Public-note policy checks; all endpoint and credential examples are synthetic."""
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate-public-notes.py"


class PublicNotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.find = staticmethod(runpy.run_path(str(SCRIPT))["find_violations"])

    def test_user_changes_and_package_info_are_allowed(self):
        text = """# BiG Retail v1.0.14（1028）
- 切换授权服务器会退出登录，需要重新激活。
- Supports Android 7.0+, ARM32 / ARM64; app com.byghitech.classicpos.
- Archivo: big-retail.apk; update.json. Se requiere reactivar.
<!-- release-package-info:start -->
- SHA-256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Size: 84418939
<!-- release-package-info:end -->
"""
        self.assertEqual(self.find(text), [])

    def test_only_approved_public_distribution_urls_are_allowed(self):
        for url in [
            "https://github.com/B-G-HITECH-S-L/bg-classic-shop-app-release/releases/tag/v1.0.14",
            "https://github.com/B-G-HITECH-S-L/bg-classic-shop-app-release/releases/download/v1.0.14/big-retail.apk",
            "https://raw.githubusercontent.com/B-G-HITECH-S-L/bg-pos-aio-release/main/application/application-catalog.json",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.find("[下载](" + url + ")"), [])

    def test_addresses_and_unapproved_links_are_rejected(self):
        for text in [
            "https://license.example.invalid", "地址203.0.113.10请勿公开",
            "地址license.example.invalid请勿公开", "2001:db8::1", "[::1]",
            "https://github.com.evil.invalid/path", "https://user:example@github.com/private/repo",
            "https://github.com/B-G-HITECH-S-L/bg-classic-shop-app-release/releases/latest?token=example",
            "localhost", "example-instance.big-aio.local",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.find(text))

    def test_encoded_and_invisible_address_variants_are_rejected(self):
        for text in [
            "２０３．０．１１３．１０", "203.0.\u200b113.10",
            "https%3A%2F%2Flicense.example.invalid", "203&#46;0&#46;113&#46;10",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.find(text))

    def test_private_material_paths_and_confirmation_details_are_rejected(self):
        for text in [
            "password=EXAMPLE_ONLY", "激活码：EXAMPLE-DO-NOT-USE",
            "ghp_" + "x" * 36, "-----BEGIN PRIVATE KEY-----",
            "/Users/example/private/report.md", r"C:\Users\example\report.md",
            "license.local.json", "pubspec.lock", "build-info.json", "sourceDirty=true",
            "私有发版确认单", "连续点击版本号 5 次进入开发设置",
            "Tap the version five times to open Developer Settings.",
            "Pulse la versión cinco veces para abrir Ajustes de desarrollo.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.find(text))

    def test_diagnostics_do_not_echo_the_offending_text(self):
        secret = "EXAMPLE-NEVER-ECHO-THIS"
        with tempfile.TemporaryDirectory() as directory:
            notes = Path(directory) / "release-notes.md"
            notes.write_text("# Safe title\npassword=" + secret + "\n", encoding="utf-8")
            before = notes.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(notes)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("第 2 行", result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual(notes.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
