#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import pathlib
import re
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory as SystemTemporaryDirectory
from urllib.parse import urlsplit
from unittest import mock, TestCase

from pyfakefs.fake_filesystem_unittest import Patcher

from continuous_delivery_scripts.plugins.python import _generate_pdoc_command_list, Python

from continuous_delivery_scripts.generate_docs import _clear_previous_docs, generate_documentation, generate_docs
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable


class TestGenerateDocs(TestCase):
    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_guides_work_with_plugin_without_api_index(self, get_value_or_default, _get_language_specifics):
        with SystemTemporaryDirectory() as temporary_root:
            project_root = pathlib.Path(temporary_root, "project")
            source = project_root / "guides"
            source.mkdir(parents=True)
            (source / "index.md").write_text("# Task guides\n", encoding="utf8")
            get_value_or_default.side_effect = lambda key, default: {
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(source),
                ConfigurationVariable.PROJECT_NAME: "Example Project",
            }.get(key, default)

            output = pathlib.Path(temporary_root, "site")
            generate_documentation(output, "another_language")

            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "guides" / "index.html").is_file())
            self.assertFalse((output / "api.html").exists())
            landing = (output / "index.html").read_text(encoding="utf8")
            self.assertIn("<h1>Example Project</h1>", landing)
            self.assertIn("<title>Example Project documentation</title>", landing)
            self.assertNotIn("Continuous Delivery Scripts", landing)
            self.assertNotIn("API reference", landing)

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default", return_value=None)
    def test_projects_without_guides_keep_their_api_index(self, _get_value_or_default, get_language_specifics):
        with SystemTemporaryDirectory() as temporary_root:
            output = pathlib.Path(temporary_root, "site")

            def generate_api(output_directory, _module):
                (output_directory / "index.html").write_text("API reference", encoding="utf8")

            get_language_specifics.return_value.generate_code_documentation.side_effect = generate_api
            generate_documentation(output, "module")

            self.assertEqual((output / "index.html").read_text(encoding="utf8"), "API reference")
            self.assertFalse((output / "api.html").exists())

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_published_project_guides_have_valid_local_links(self, get_value_or_default, get_language_specifics):
        project_root = pathlib.Path(__file__).resolve().parents[2]
        get_value_or_default.side_effect = lambda key, default: {
            ConfigurationVariable.PROJECT_ROOT: str(project_root),
            ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(project_root / "guides"),
            ConfigurationVariable.DOCUMENTATION_GUIDES_OUTPUT_FOLDER: "guides",
        }.get(key, default)

        def generate_api(output_directory, _module):
            (output_directory / "index.html").write_text("API reference", encoding="utf8")

        get_language_specifics.return_value.generate_code_documentation.side_effect = generate_api
        with SystemTemporaryDirectory() as temporary_root:
            output = pathlib.Path(temporary_root, "site")
            generate_documentation(output, "continuous_delivery_scripts")

            for page in output.rglob("*.html"):
                html = page.read_text(encoding="utf8")
                for href in re.findall(r'href="([^"]+)"', html):
                    target = urlsplit(href)
                    if not target.scheme and target.path:
                        with self.subTest(page=page.name, href=href):
                            self.assertTrue((page.parent / target.path).is_file())

    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    @mock.patch("continuous_delivery_scripts.generate_docs.configuration.get_value_or_default")
    def test_publishes_guides_and_preserves_api_index(self, get_value_or_default, get_language_specifics):
        with SystemTemporaryDirectory() as temporary_root:
            project_root = pathlib.Path(temporary_root, "project")
            guides = project_root / "guides"
            guides.mkdir(parents=True)
            (guides / "index.md").write_text(
                "<!--\nCopyright notice\n-->\n# Guides\n\n[SPDX](generating-an-spdx-sbom.md)\n", encoding="utf8"
            )
            (guides / "generating-an-spdx-sbom.md").write_text(
                "<!--\nCopyright notice\n-->\n# Generate an SPDX SBOM\n\n"
                "Guide text about SPDX reporting.\n\n"
                "```bash\ncd-generate-spdx --output-dir spdx-output\n```\n",
                encoding="utf8",
            )
            (project_root / "llms.txt").write_text("# Tool map\n", encoding="utf8")
            get_value_or_default.side_effect = lambda key, _default: {
                ConfigurationVariable.PROJECT_ROOT: str(project_root),
                ConfigurationVariable.DOCUMENTATION_GUIDES_DIR: str(guides),
                ConfigurationVariable.DOCUMENTATION_GUIDES_OUTPUT_FOLDER: "reference/guides",
                ConfigurationVariable.PROJECT_NAME: "Another Project",
                ConfigurationVariable.FILE_LICENCE_IDENTIFIER: "MIT",
            }.get(key)
            output = pathlib.Path(temporary_root, "site")

            def generate_api(output_directory, _module):
                (output_directory / "index.html").write_text("API reference", encoding="utf8")
                (output_directory / "module.html").write_text('<a href="index.html">Package API</a>', encoding="utf8")
                subpackage = output_directory / "subpackage"
                subpackage.mkdir()
                (subpackage / "index.html").write_text("Subpackage API", encoding="utf8")
                (subpackage / "module.html").write_text(
                    '<a href="../index.html">Package API</a><a href="index.html">Subpackage API</a>',
                    encoding="utf8",
                )

            get_language_specifics.return_value.generate_code_documentation.side_effect = generate_api

            generate_documentation(output, "continuous_delivery_scripts")

            self.assertEqual((output / "api.html").read_text(encoding="utf8"), "API reference")
            self.assertIn("<h1>Another Project</h1>", (output / "index.html").read_text(encoding="utf8"))
            self.assertIn("<p>Project licence: MIT</p>", (output / "index.html").read_text(encoding="utf8"))
            self.assertIn(">Generate an SPDX SBOM</a>", (output / "index.html").read_text(encoding="utf8"))
            self.assertNotIn("&lt;!--", (output / "index.html").read_text(encoding="utf8"))
            self.assertNotIn("third_party_IP_report.html", (output / "index.html").read_text(encoding="utf8"))
            self.assertIn(
                "Generate an SPDX SBOM — Another Project.",
                (output / "reference" / "guides" / "generating-an-spdx-sbom.html").read_text(encoding="utf8"),
            )
            self.assertIn(
                "<title>Generate an SPDX SBOM</title>",
                (output / "reference" / "guides" / "generating-an-spdx-sbom.html").read_text(encoding="utf8"),
            )
            guide_text = (output / "reference" / "guides" / "generating-an-spdx-sbom.html").read_text(encoding="utf8")
            self.assertIn("<h1>Generate an SPDX SBOM</h1>", guide_text)
            self.assertIn("<p>Guide text about SPDX reporting.</p>", guide_text)
            self.assertNotIn("&lt;!--", guide_text)
            self.assertIn('href="api.html"', (output / "module.html").read_text(encoding="utf8"))
            self.assertIn('href="../api.html"', (output / "subpackage" / "module.html").read_text(encoding="utf8"))
            self.assertIn('href="index.html"', (output / "subpackage" / "module.html").read_text(encoding="utf8"))
            self.assertIn(
                "reference/guides/generating-an-spdx-sbom.html", (output / "index.html").read_text(encoding="utf8")
            )
            self.assertIn(
                'href="generating-an-spdx-sbom.html"',
                (output / "reference" / "guides" / "index.html").read_text(encoding="utf8"),
            )
            self.assertIn(
                "cd-generate-spdx --output-dir spdx-output",
                (output / "reference" / "guides" / "generating-an-spdx-sbom.html").read_text(encoding="utf8"),
            )
            self.assertIn(
                'href="../../index.html"', (output / "reference" / "guides" / "index.html").read_text(encoding="utf8")
            )
            self.assertEqual((output / "llms.txt").read_text(encoding="utf8"), "# Tool map\n")

    def test_clear_previous_docs(self):
        with Patcher() as patcher:
            fake_output_dir = pathlib.Path("local_docs")
            patcher.fs.create_file(
                str(fake_output_dir.joinpath("some_docs_file.html")), contents="This is some old documentation."
            )
            self.assertTrue(fake_output_dir.is_dir())

            _clear_previous_docs(fake_output_dir)
            self.assertFalse(fake_output_dir.is_dir())

    def test_clear_previous_docs_none_exist(self):
        fake_output_dir = pathlib.Path("local_docs")
        if fake_output_dir.exists():
            fake_output_dir.rmdir()
        self.assertFalse(fake_output_dir.is_dir())

        _clear_previous_docs(fake_output_dir)

    @mock.patch("continuous_delivery_scripts.generate_docs._clear_previous_docs")
    @mock.patch("continuous_delivery_scripts.plugins.python.check_call")
    @mock.patch("continuous_delivery_scripts.plugins.python.TemporaryDirectory")
    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    def test_generate_docs(self, get_language_specifics, TemporaryDirectory, check_call, _clear_previous_docs):
        get_language_specifics.return_value = Python()
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"
        with Patcher():
            temp_dir = pathlib.Path("temp")
            TemporaryDirectory.return_value.__enter__.return_value = temp_dir
            result = generate_docs(fake_output_dir, fake_module)

            self.assertEqual(result, 0)
            _clear_previous_docs.assert_called_once_with(fake_output_dir)
            check_call.assert_called_once_with(_generate_pdoc_command_list(temp_dir, fake_module))

    @mock.patch("continuous_delivery_scripts.generate_docs._clear_previous_docs")
    @mock.patch("continuous_delivery_scripts.generate_docs.log_exception")
    @mock.patch("continuous_delivery_scripts.plugins.python.check_call")
    @mock.patch("continuous_delivery_scripts.plugins.python.TemporaryDirectory")
    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    def test_generate_docs_errors(
        self, get_language_specifics, TemporaryDirectory, check_call, log_exception, _clear_previous_docs
    ):
        get_language_specifics.return_value = Python()
        check_call.side_effect = CalledProcessError(returncode=2, cmd=["pdoc", "some", "stuff"])
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"
        with Patcher():
            temp_dir = pathlib.Path("temp")
            TemporaryDirectory.return_value = temp_dir

            result = generate_docs(fake_output_dir, fake_module)

            self.assertEqual(result, 1)
            _clear_previous_docs.assert_called_once_with(fake_output_dir)
            check_call.assert_called_once_with(_generate_pdoc_command_list(temp_dir, fake_module))
            log_exception.assert_called_once()

    @mock.patch("continuous_delivery_scripts.plugins.python.TemporaryDirectory")
    @mock.patch("continuous_delivery_scripts.plugins.python._call_pdoc")
    @mock.patch("continuous_delivery_scripts.generate_docs.get_language_specifics")
    def test_update_docs(self, get_language_specifics, _call_pdoc, TemporaryDictionary):
        with Patcher() as patcher:
            temp_dir = pathlib.Path("temp")
            TemporaryDictionary.return_value = temp_dir
            get_language_specifics.return_value = Python()

            module_name = "module_name"
            docs_dir = pathlib.Path("docs")

            def mocked_pdoc(output_directory, module):
                # Creating some fake files in a same way as Pdoc
                if not output_directory.exists():
                    patcher.fs.create_dir(output_directory)
                docs_contents_dir = output_directory.joinpath(module)
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("docs_file.html")), contents="This is some documentation."
                )
                # check that it moves subdirectories too
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("sub_dir", "docs_file.html")),
                    contents="This is some more documentation.",
                )

            _call_pdoc.side_effect = mocked_pdoc

            patcher.fs.create_file(
                str(docs_dir.joinpath("old_docs_file.html")), contents="This is some old documentation."
            )
            self.assertTrue(docs_dir.joinpath("old_docs_file.html").exists())

            generate_documentation(docs_dir, module_name)

            _call_pdoc.assert_called_once_with(temp_dir, module_name)

            # Check that old documentation in the output directory has been removed
            self.assertFalse(docs_dir.joinpath("old_docs_file.html").exists())
            # Check that module name directory is not present in the output directory
            self.assertTrue(docs_dir.joinpath("docs_file.html").is_file())
            self.assertTrue(docs_dir.joinpath("sub_dir", "docs_file.html").is_file())
            self.assertFalse(docs_dir.joinpath(module_name).exists())
