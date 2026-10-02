#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest
from email.parser import Parser
from tempfile import TemporaryDirectory
from unittest import mock

from pathlib import Path

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.package_helpers import LicenceSource, PackageMetadata
from continuous_delivery_scripts.utils.python.package_helpers import (
    PythonProjectMetadataFetcher,
    parse_package_metadata,
    parse_package_metadata_lines,
    get_all_packages_metadata_lines,
)


class TestPackaging(unittest.TestCase):
    def test_language_plugin_can_supply_named_package_fields(self):
        metadata = PackageMetadata.from_fields(
            name="example.com/dependency",
            version="v1.2.3",
            licence="MIT",
            licence_source=LicenceSource.EXPRESSION,
            url="https://example.com/LICENSE",
            licence_evidence=[{"kind": "licence", "path": "https://example.com/LICENSE", "text": ""}],
        )

        self.assertEqual(metadata.name, "example.com/dependency")
        self.assertEqual(metadata.version, "v1.2.3")
        self.assertEqual(metadata.licence_source, "License-Expression")
        self.assertFalse(metadata.has_unknown_licence)
        self.assertEqual(metadata.declared_licence, "MIT")
        self.assertEqual(metadata.url, "https://example.com/LICENSE")
        self.assertEqual(len(metadata.licence_evidence), 1)

    def test_parse_metadata(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "PKG-INFO")
        with open(str(test_file), "r", encoding="utf8") as f:
            metadata = parse_package_metadata_lines(f.readlines())
        self.assertIsNotNone(metadata)
        self.assertEqual("mbed-tools-ci-scripts", metadata.name)
        self.assertEqual("Apache 2.0", metadata.licence)
        self.assertEqual("1.5.1", metadata.version)
        self.assertEqual("Mbed team", metadata.author)
        self.assertEqual("support@mbed.com", metadata.author_email)
        self.assertEqual("https://github.com/ARMmbed/mbed-tools-ci-scripts", metadata.url)
        self.assertEqual("Continuous Integration scripts used by Mbed tools Python packages", metadata.description)

    def test_project_metadata_generation_and_parsing(self):
        current_package = configuration.get_value(ConfigurationVariable.PACKAGE_NAME)
        metadata = get_all_packages_metadata_lines(current_package)
        self.assertIsNotNone(metadata)
        self.assertGreaterEqual(len(metadata), 1)
        self.assertIn(
            current_package, [parse_package_metadata_lines(metadata_lines).name for metadata_lines in metadata]
        )

    def test_package_metadata_parser(self):
        current_package = configuration.get_value(ConfigurationVariable.PACKAGE_NAME)
        parser = PythonProjectMetadataFetcher(package_name=current_package)
        metadata = parser.project_metadata
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.package_name, current_package)
        self.assertIsNotNone(metadata.project_metadata)
        self.assertEqual(metadata.project_metadata.name, current_package)
        self.assertEqual(metadata.package_name, current_package)
        self.assertIsNotNone(metadata.dependencies_metadata)
        self.assertGreaterEqual(len(metadata.dependencies_metadata), 1)

    def test_prefer_spdx_licence_expression(self):
        metadata = parse_package_metadata_lines(
            ["Name: example", "License: Legacy licence text", "License-Expression: MIT OR Apache-2.0"]
        )

        self.assertEqual(metadata.licence, "MIT OR Apache-2.0")

    def test_uses_licence_classifier_when_legacy_field_is_copyright_notice(self):
        metadata = parse_package_metadata_lines(
            [
                "Name: example",
                "License: Copyright (C) the authors",
                "Classifier: License :: OSI Approved :: MIT License",
            ]
        )

        self.assertEqual(metadata.licence, "MIT")

    def test_uses_licence_classifier_when_legacy_field_contains_full_licence_text(self):
        metadata = parse_package_metadata_lines(
            [
                "Name: example",
                "License: MIT License",
                " ",
                " Permission is hereby granted, free of charge, to any person obtaining a copy",
                "Classifier: License :: OSI Approved :: MIT License",
            ]
        )

        self.assertEqual(metadata.licence, "MIT")
        self.assertEqual(metadata.licence_source, "License-Classifier")
        self.assertIn("Permission is hereby granted", metadata.declared_licence)

    def test_retains_all_licence_classifiers_and_their_source(self):
        metadata = parse_package_metadata_lines(
            [
                "Name: example",
                "Classifier: License :: OSI Approved :: MIT License",
                "Classifier: License :: OSI Approved :: Apache Software License",
            ]
        )

        self.assertEqual(metadata.licence_classifiers, ["MIT License", "Apache Software License"])
        self.assertEqual(metadata.licence_candidates, ["MIT", "Apache-2.0"])
        self.assertEqual(metadata.licence_source, "unknown")

    def test_unrecognised_classifiers_are_kept_for_review(self):
        metadata = parse_package_metadata_lines(
            [
                "Name: example",
                "Classifier: License :: Public Domain",
                "Classifier: License :: OSI Approved :: MIT License",
            ]
        )

        self.assertEqual(metadata.licence_source, "unknown")
        self.assertEqual(metadata.licence_classifiers, ["Public Domain", "MIT License"])

    def test_preserves_multiline_metadata(self):
        metadata = parse_package_metadata_lines(
            ["Name: example", "License: This licence contains", "  several lines of text", "Version: 1.0"]
        )

        self.assertIn("several lines of text", metadata.declared_licence)

    def test_reads_installed_licence_and_notice_evidence(self):
        with TemporaryDirectory() as folder:
            dist_info = Path(folder, "example-1.0.dist-info")
            licence = dist_info / "licenses" / "LICENSE"
            licence.parent.mkdir(parents=True)
            licence.write_text("MIT licence text", encoding="utf8")
            notice = dist_info / "NOTICE"
            notice.write_text("Notice text", encoding="utf8")
            distribution = mock.Mock()
            distribution.files = [
                Path("example-1.0.dist-info/licenses/LICENSE"),
                Path("example-1.0.dist-info/NOTICE"),
            ]
            distribution.locate_file.side_effect = lambda entry: Path(folder, entry)

            metadata = parse_package_metadata(
                Parser().parsestr("Name: example\nLicense-Expression: MIT\nLicense-File: LICENSE\n"), distribution
            )

            self.assertEqual([item["kind"] for item in metadata.licence_evidence], ["licence", "notice"])
            self.assertEqual(metadata.licence_evidence[0]["text"], "MIT licence text")

    @mock.patch("continuous_delivery_scripts.utils.python.package_helpers._get_distribution")
    def test_missing_dependency_is_recorded(self, get_distribution):
        from importlib.metadata import PackageNotFoundError

        root = mock.Mock()
        root.name = "example"
        root.metadata = Parser().parsestr("Name: example\nLicense-Expression: MIT\n")
        root.requires = ["missing-package>=1"]
        root.files = []

        def find_distribution(name):
            if name == "example":
                return root
            raise PackageNotFoundError(name)

        get_distribution.side_effect = find_distribution

        project = PythonProjectMetadataFetcher("example").project_metadata

        self.assertEqual(project.missing_dependencies, ["missing-package"])

    @mock.patch("continuous_delivery_scripts.utils.python.package_helpers._get_distribution")
    def test_dependencies_of_requested_extras_are_included(self, get_distribution):
        def distribution(name, requirements):
            result = mock.Mock()
            result.name = name
            result.metadata = Parser().parsestr(f"Name: {name}\nLicense-Expression: MIT\n")
            result.requires = requirements
            result.files = []
            return result

        distributions = {
            "example": distribution("example", ["addon[feature]"]),
            "addon": distribution("addon", ['optional; extra == "feature"']),
            "optional": distribution("optional", []),
        }
        get_distribution.side_effect = distributions.__getitem__

        project = PythonProjectMetadataFetcher("example").project_metadata

        self.assertEqual([entry.name for entry in project.dependencies_metadata], ["addon", "optional"])
