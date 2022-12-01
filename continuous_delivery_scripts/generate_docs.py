#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Generates documentation."""
import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


def _clear_previous_docs(output_directory: Path) -> None:
    """Removes the existing output directory to avoid stale docs pages."""
    if output_directory.is_dir():
        shutil.rmtree(str(output_directory))


def generate_documentation(output_directory: Path, module_to_document: str) -> None:
    """Generates the documentation."""
    _clear_previous_docs(output_directory)
    os.makedirs(str(output_directory), exist_ok=True)
    get_language_specifics().generate_code_documentation(output_directory, module_to_document)


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
