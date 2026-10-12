#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Checks public documentation discovery files without contacting an external site."""

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from xml.etree import ElementTree

from continuous_delivery_scripts.generate_docs import generate_documentation
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable
from continuous_delivery_scripts.utils.documentation_discovery import (
    documentation_site_url,
    publish_discovery_files,
)


class TestDocumentationDiscovery(TestCase):
    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_authored_files_are_selected_per_file_from_root_guides_then_module(self, get_config, plugin):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            guides = root / "guides"
            guides.mkdir()
            (guides / "index.md").write_text("# Guides\n", encoding="utf8")
            module = root / "package"
            module.mkdir()
            (root / "robots.txt").write_text("Root robots\n", encoding="utf8")
            (guides / "robots.txt").write_text("Guide robots\n", encoding="utf8")
            (module / "robots.txt").write_text("Module robots\n", encoding="utf8")
            (guides / "sitemap.xml").write_text("Guide sitemap\n", encoding="utf8")
            (module / "sitemap.xml").write_text("Module sitemap\n", encoding="utf8")
            (module / "llms.txt").write_text("# Module index\n", encoding="utf8")
            settings = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(guides),
                ConfigurationVariable.SOURCE_DIR: str(module),
                ConfigurationVariable.PROJECT_NAME: "Example Project",
                ConfigurationVariable.DOCUMENTATION_SITE_URL: "https://example.org/project/",
            }
            get_config.side_effect = lambda key, default: settings.get(key, default)
            plugin.return_value.generate_code_documentation.side_effect = lambda output, _module: (
                output / "index.html"
            ).write_text("<html>API</html>", encoding="utf8")
            output = root / "published"
            generate_documentation(output, "package")
            self.assertEqual((output / "robots.txt").read_text(encoding="utf8"), "Root robots\n")
            self.assertEqual((output / "sitemap.xml").read_text(encoding="utf8"), "Guide sitemap\n")
            self.assertEqual((output / "llms.txt").read_text(encoding="utf8"), "# Module index\n")
            self.assertTrue((output / "llms-full.txt").is_file())

            (root / "robots.txt").unlink()
            generate_documentation(output, "package")
            self.assertEqual((output / "robots.txt").read_text(encoding="utf8"), "Guide robots\n")
            (guides / "robots.txt").unlink()
            generate_documentation(output, "package")
            self.assertEqual((output / "robots.txt").read_text(encoding="utf8"), "Module robots\n")

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_module_and_guides_overrides_do_not_require_a_rendered_guide_index(self, get_config, plugin):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            guides = root / "guides"
            guides.mkdir()
            (guides / "robots.txt").write_text("Guide robots\n", encoding="utf8")
            module = root / "src" / "package"
            module.mkdir(parents=True)
            (module / "llms-full.txt").write_text("# Module documentation\n", encoding="utf8")
            settings = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(guides),
                ConfigurationVariable.SOURCE_DIR: "src",
            }
            get_config.side_effect = lambda key, default: settings.get(key, default)
            plugin.return_value.generate_code_documentation.side_effect = lambda output, _module: (
                output / "index.html"
            ).write_text("<html>API</html>", encoding="utf8")
            output = root / "published"
            generate_documentation(output, "package")
            self.assertEqual((output / "robots.txt").read_text(encoding="utf8"), "Guide robots\n")
            self.assertEqual((output / "llms-full.txt").read_text(encoding="utf8"), "# Module documentation\n")
            self.assertFalse((output / "sitemap.xml").exists())

    @mock.patch("continuous_delivery_scripts.utils.documentation_discovery.github_pages_url")
    @mock.patch("continuous_delivery_scripts.utils.documentation_discovery.get_project_remote_url")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_uses_verified_github_pages_when_url_is_not_configured(self, get_config, get_remote, pages_url):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            get_config.side_effect = lambda key, default: (
                str(root) if key == ConfigurationVariable.PROJECT_ROOT else default
            )
            get_remote.return_value = "git@github.com:ARMmbed/example.git"
            pages_url.return_value = "https://armmbed.github.io/example/"
            self.assertEqual(documentation_site_url(), "https://armmbed.github.io/example/")
            get_remote.assert_called_once_with(root)
            pages_url.assert_called_once_with("git@github.com:ARMmbed/example.git")

            pages_url.return_value = None
            self.assertIsNone(documentation_site_url())

    @mock.patch("continuous_delivery_scripts.utils.documentation_discovery.github_pages_url")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_explicit_site_url_takes_precedence_over_github(self, get_config, pages_url):
        get_config.side_effect = lambda key, default: (
            "https://docs.example.org/project" if key == ConfigurationVariable.DOCUMENTATION_SITE_URL else default
        )
        self.assertEqual(documentation_site_url(), "https://docs.example.org/project/")
        pages_url.assert_not_called()

    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_existing_rendered_guides_gain_metadata_only_once(self, get_config):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            guides = root / "guides"
            guides.mkdir()
            (guides / "index.md").write_text("# Task guides\n", encoding="utf8")
            output = root / "published"
            rendered = output / "guides"
            rendered.mkdir(parents=True)
            html = '<html><head><title>Task guides</title><meta name="description" content="Task guides."></head><body></body></html>'
            (output / "index.html").write_text(html, encoding="utf8")
            (rendered / "index.html").write_text(html, encoding="utf8")
            get_config.side_effect = lambda key, default: (
                "https://example.org/project/" if key == ConfigurationVariable.DOCUMENTATION_SITE_URL else default
            )

            for _ in range(2):
                publish_discovery_files(output, root, guides, Path("guides"), "Example Project")

            for page in (output / "index.html", rendered / "index.html"):
                self.assertEqual(page.read_text(encoding="utf8").count('type="application/ld+json"'), 1)
            self.assertIn(
                "https://example.org/project/guides/index.html", (rendered / "index.html").read_text(encoding="utf8")
            )

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_publishes_only_generated_pages_and_preserves_authored_llms(self, get_config, plugin):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            guides = root / "guides"
            guides.mkdir()
            (guides / "index.md").write_text("# Guides\n\n[Example](example.md)\n", encoding="utf8")
            (guides / "example.md").write_text("# Example\n\n## Steps\n\nUse the [guide](index.md).\n", encoding="utf8")
            (root / "llms.txt").write_text("# Authored index\n", encoding="utf8")
            settings = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(guides),
                ConfigurationVariable.DOCUMENTATION_GUIDES_OUTPUT_FOLDER: "guides",
                ConfigurationVariable.PROJECT_NAME: "Example Project",
                ConfigurationVariable.DOCUMENTATION_SITE_URL: "https://example.org/project/",
            }
            get_config.side_effect = lambda key, default: settings.get(key, default)

            def generate_api(output, _module):
                (output / "index.html").write_text("<html><body>API</body></html>", encoding="utf8")

            plugin.return_value.generate_code_documentation.side_effect = generate_api
            output = root / "published"
            generate_documentation(output, "module")

            self.assertEqual((output / "llms.txt").read_text(encoding="utf8"), "# Authored index\n")
            self.assertEqual(
                (output / "robots.txt").read_text(encoding="utf8"),
                "User-agent: *\nAllow: /\nSitemap: https://example.org/project/sitemap.xml\n",
            )
            sitemap = ElementTree.parse(output / "sitemap.xml")
            urls = [element.text for element in sitemap.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
            self.assertEqual(
                urls,
                [
                    "https://example.org/project/api.html",
                    "https://example.org/project/guides/example.html",
                    "https://example.org/project/guides/index.html",
                    "https://example.org/project/",
                ],
            )
            full = (output / "llms-full.txt").read_text(encoding="utf8")
            self.assertIn("## Example", full)
            self.assertIn("### Steps", full)
            self.assertIn("[guide](https://example.org/project/guides/index.html)", full)
            self.assertNotIn("[guide](index.md)", full)
            self.assertIn("[Generated API reference](https://example.org/project/api.html)", full)
            for page, expected_type in (
                (output / "index.html", "WebSite"),
                (output / "guides/example.html", "TechArticle"),
            ):
                content = page.read_text(encoding="utf8")
                payload = re.search(r'<script type="application/ld\+json">(.*?)</script>', content)
                self.assertIsNotNone(payload)
                self.assertEqual(json.loads(payload.group(1))["@type"], expected_type)

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_does_not_invent_site_urls_and_respects_existing_files(self, get_config, plugin):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            (root / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n", encoding="utf8")
            (root / "sitemap.xml").write_text("<authored />\n", encoding="utf8")
            (root / "llms-full.txt").write_text("# Authored full documentation\n", encoding="utf8")
            get_config.side_effect = lambda key, default: (
                str(root) if key == ConfigurationVariable.PROJECT_ROOT else default
            )

            def generate_api(output, _module):
                (output / "index.html").write_text("<html><body>API</body></html>", encoding="utf8")

            plugin.return_value.generate_code_documentation.side_effect = generate_api
            output = root / "published"
            generate_documentation(output, "module")
            self.assertEqual((output / "robots.txt").read_text(encoding="utf8"), "User-agent: *\nDisallow: /private/\n")
            self.assertEqual((output / "llms-full.txt").read_text(encoding="utf8"), "# Authored full documentation\n")
            self.assertEqual((output / "sitemap.xml").read_text(encoding="utf8"), "<authored />\n")
            self.assertFalse((output / "llms.txt").exists())

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_generates_llms_index_only_for_existing_pages(self, get_config, plugin):
        with TemporaryDirectory() as temporary_root:
            root = Path(temporary_root)
            settings = {
                ConfigurationVariable.PROJECT_ROOT: str(root),
                ConfigurationVariable.PROJECT_NAME: "Example Project",
                ConfigurationVariable.DOCUMENTATION_SITE_URL: "https://example.org/project/",
            }
            get_config.side_effect = lambda key, default: settings.get(key, default)

            def generate_api(output, _module):
                (output / "index.html").write_text("<html><body>API</body></html>", encoding="utf8")

            plugin.return_value.generate_code_documentation.side_effect = generate_api
            output = root / "published"
            generate_documentation(output, "module")
            index = (output / "llms.txt").read_text(encoding="utf8")
            self.assertIn("[Overview](https://example.org/project/)", index)
            self.assertNotIn("API reference", index)
            self.assertFalse((output / "llms-full.txt").exists())
