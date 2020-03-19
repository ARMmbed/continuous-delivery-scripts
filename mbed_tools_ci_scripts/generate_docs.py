#
# Copyright (c) 2020, Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Generates documentation using Pdoc."""
import os
import shutil
import sys

import argparse
import logging
from pathlib import Path
from subprocess import check_call
from typing import List

from mbed_tools_ci_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from mbed_tools_ci_scripts.utils.filesystem_helpers import TemporaryDirectory
from mbed_tools_ci_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


def _clear_previous_docs(output_directory: Path) -> None:
    """Removes the existing output directory to avoid stale docs pages."""
    if output_directory.is_dir():
        shutil.rmtree(str(output_directory))


def _generate_pdoc_command_list(output_directory: Path, module: str) -> List[str]:
    return [
        "pdoc",
        "--html",
        f"{module}",
        "--output-dir",
        f"{str(output_directory)}",
        "--force",
        "--config",
        "show_type_annotations=True",
    ]


def generate_documentation(output_directory: Path, module_to_document: str) -> None:
    """Ensures the documentation is in the correct location.

    Pdoc nests its docs output in a folder with the module's name.
    This process removes this unwanted folder.
    """
    _clear_previous_docs(output_directory)
    os.makedirs(str(output_directory), exist_ok=True)
    with TemporaryDirectory() as temp_dir:
        _call_pdoc(temp_dir, module_to_document)
        docs_contents_dir = temp_dir.joinpath(module_to_document)
        if docs_contents_dir.exists() and docs_contents_dir.is_dir():
            for element in docs_contents_dir.iterdir():
                shutil.move(str(element), str(output_directory))


def _call_pdoc(output_directory: Path, module: str) -> None:
    """Calls Pdoc for generating the docs."""
    logger.info("Creating Pdoc documentation.")
    command_list = _generate_pdoc_command_list(output_directory, module)
    check_call(command_list)


def generate_docs(output_directory: Path, module: str) -> int:
    """Triggers building the documentation."""
    try:
        generate_documentation(output_directory, module)
    except Exception as e:
        log_exception(logger, e)
        return 1
    return 0


def main() -> None:
    """Parses command line arguments and generates docs."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output_directory",
        help="Output directory for docs html files.",
        default=configuration.get_value(ConfigurationVariable.DOCUMENTATION_DEFAULT_OUTPUT_PATH),
    )
    args = parser.parse_args()
    output_directory = Path(args.output_directory)
    module = configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)
    sys.exit(generate_docs(output_directory=output_directory, module=module))


if __name__ == "__main__":
    main()
