#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import time
import unittest

from continuous_delivery_scripts.language_specifics import fetch_project_language_plugin, all_language_plugins
from continuous_delivery_scripts.plugins import all_plugin_files


class TestPlugins(unittest.TestCase):
    def test_plugin_existence(self):
        self.assertIsNotNone(all_plugin_files)
        self.assertGreater(len(all_language_plugins()), 0)

    def test_fetch_plugin_success(self):
        all_plugins = all_language_plugins()
        for plugin in all_plugin_files:
            pluginImpl = fetch_project_language_plugin(all_plugins, plugin)
            self.assertIsNotNone(pluginImpl)
            self.assertIsNotNone(f"{pluginImpl}")
            pluginImpl = fetch_project_language_plugin(all_plugins, plugin.upper())
            self.assertIsNotNone(pluginImpl)
            self.assertIsNotNone(f"{pluginImpl}")
            pluginImpl = fetch_project_language_plugin(all_plugins, plugin.lower())
            self.assertIsNotNone(pluginImpl)
            self.assertIsNotNone(f"{pluginImpl}")

    def test_fetch_plugin_failure(self):
        all_plugins = all_language_plugins()
        invalidPlugin = f"{all_plugin_files[0]}{time.time()}"
        print(invalidPlugin)
        pluginImpl = fetch_project_language_plugin(all_plugins, invalidPlugin)
        self.assertIsNone(pluginImpl)
        pluginImpl = fetch_project_language_plugin(all_plugins, invalidPlugin.upper())
        self.assertIsNone(pluginImpl)
        pluginImpl = fetch_project_language_plugin(all_plugins, invalidPlugin.lower())
        self.assertIsNone(pluginImpl)
