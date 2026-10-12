#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Load bundled documentation templates with HTML-only escaping."""

from pathlib import Path

import jinja2


def documentation_templates() -> jinja2.Environment:
    """Return the shared Jinja2 environment for HTML and discovery text files."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(Path(__file__).resolve().parents[1] / "templates")),
        autoescape=lambda name: bool(name and name.endswith(".html.jinja2")),
        keep_trailing_newline=True,
    )
