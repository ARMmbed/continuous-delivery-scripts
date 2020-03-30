#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import unittest

from pathlib import Path

from mbed_tools_ci_scripts.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci_scripts.utils.package_helpers import (
    ProjectMetadataParser,
    parse_package_metadata_lines,
    generate_package_info,
    get_all_packages_metadata_lines,
)


class TestPackaging(unittest.TestCase):
    def test_parse_metadata(self):
        test_file = Path(__file__).parent.joinpath("fixtures", "PKG-INFO")
        with open(str(test_file), "r") as f:
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
        generate_package_info()
        current_package = configuration.get_value(ConfigurationVariable.PACKAGE_NAME)
        metadata = get_all_packages_metadata_lines(current_package)
        self.assertIsNotNone(metadata)
        self.assertGreaterEqual(len(metadata), 1)
        self.assertIn(
            current_package, [parse_package_metadata_lines(metadata_lines).name for metadata_lines in metadata]
        )

    def test_package_metadata_parser(self):
        generate_package_info()
        current_package = configuration.get_value(ConfigurationVariable.PACKAGE_NAME)
        parser = ProjectMetadataParser(package_name=current_package)
        metadata = parser.project_metadata
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.package_name, current_package)
        self.assertIsNotNone(metadata.project_metadata)
        self.assertEqual(metadata.project_metadata.name, current_package)
        self.assertEqual(metadata.package_name, current_package)
        self.assertIsNotNone(metadata.dependencies_metadata)
        self.assertGreaterEqual(len(metadata.dependencies_metadata), 1)
