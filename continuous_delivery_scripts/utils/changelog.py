#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers for generating and repairing changelogs."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Iterator, Optional

import toml

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.filesystem_helpers import cd

_MARKDOWN_CHANGELOG_SUFFIXES = {".md", ".markdown"}
_RELEASE_TITLE_PATTERN = re.compile(r'^"?[vV]?\d+\.\d+\.\d+[^\n]*$')


def generate_changelog(version: Optional[str]) -> None:
    """Builds the changelog with Towncrier and normalises Markdown output when needed."""
    project_config_path = configuration.get_value(ConfigurationVariable.PROJECT_CONFIG)
    with _create_towncrier_workaround_config(project_config_path) as workaround_config_path:
        # See Towncrier's build command docs:
        # https://towncrier.readthedocs.io/en/stable/cli.html#build
        command = ["towncrier", "build", "--yes", "--name", "", "--version", str(version)]
        if workaround_config_path:
            command.extend(["--config", workaround_config_path])

        with cd(os.path.dirname(project_config_path)):
            subprocess.check_call(command)

    # FIXME: Remove this workaround when https://github.com/twisted/towncrier/issues/758 is fixed.
    normalise_markdown_release_headings(version)


def normalise_markdown_release_headings(version: Optional[str]) -> None:
    """Promote the latest markdown release title to a heading when Towncrier omits it."""
    if not version:
        return

    changelog_path = Path(str(configuration.get_value(ConfigurationVariable.CHANGELOG_FILE_PATH)))
    if changelog_path.suffix.lower() not in _MARKDOWN_CHANGELOG_SUFFIXES or not changelog_path.exists():
        return

    original = changelog_path.read_text(encoding="utf8")
    lines = original.splitlines()
    version_index = next(
        (index for index, line in enumerate(lines) if line.startswith(f"{version} ") and not line.startswith("#")),
        None,
    )
    if version_index is None:
        return

    next_release_index = next(
        (
            index
            for index in range(version_index + 1, len(lines))
            if _RELEASE_TITLE_PATTERN.match(lines[index]) and not lines[index].startswith("#")
        ),
        len(lines),
    )
    section_indexes = [index for index in range(version_index + 1, next_release_index) if lines[index].startswith("# ")]
    if not section_indexes:
        return

    lines[version_index] = f"# {lines[version_index]}"
    for index in section_indexes:
        lines[index] = f"#{lines[index]}"

    rendered = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    if rendered != original:
        changelog_path.write_text(rendered, encoding="utf8")


def _title_format_has_markdown_heading(title_format: str) -> bool:
    """Checks whether a Towncrier title format already defines a Markdown heading."""
    return any(line.lstrip().startswith("#") for line in title_format.splitlines() if line.strip())


@contextmanager
def _create_towncrier_workaround_config(project_config_path: str) -> Iterator[Optional[str]]:
    """Yields a temporary Towncrier config with a Markdown title heading if needed."""
    # FIXME: Remove this workaround when https://github.com/twisted/towncrier/issues/758 is fixed.
    # Towncrier documents Markdown title handling under title_format:
    # https://towncrier.readthedocs.io/en/stable/configuration.html#title-format
    config = toml.load(project_config_path)
    towncrier_config = config.get("tool", {}).get("towncrier", {})
    title_format = towncrier_config.get("title_format")
    if not isinstance(title_format, str) or _title_format_has_markdown_heading(title_format):
        yield None
        return

    config["tool"]["towncrier"]["title_format"] = f"# {title_format}"
    config_dir = os.path.dirname(project_config_path)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf8", suffix=".toml", prefix="towncrier-", dir=config_dir, delete=False
    ) as temp_config:
        toml.dump(config, temp_config)

    try:
        yield temp_config.name
    finally:
        os.remove(temp_config.name)
