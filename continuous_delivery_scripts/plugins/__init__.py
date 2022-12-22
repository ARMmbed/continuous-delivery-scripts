#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Language specific actions."""
import glob
from pathlib import Path

all_plugin_files = [
    Path(filename).stem
    for filename in glob.glob(str(Path(__file__).parent.joinpath("*.py")))
    if not filename.endswith("__init__.py")
]
__all__ = all_plugin_files
