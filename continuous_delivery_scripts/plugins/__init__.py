#
# Copyright (C) 2020-2021 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Language specific actions."""
import glob
import os

all_plugin_files = [
    os.path.splitext(os.path.basename(filename))[0]
    for filename in glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
]
__all__ = all_plugin_files
