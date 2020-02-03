"""Generates documentation using Pdoc."""
import argparse
import logging
import sys
import shutil
from subprocess import check_call
from pathlib import Path
from typing import List

from mbed_tools_ci_scripts.utils.configuration import (
    configuration,
    ConfigurationVariable,
)
from mbed_tools_ci_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


def _clear_previous_docs(output_directory: Path) -> None:
    """Removes the existing output directory to avoid stale docs pages."""
    if output_directory.is_dir():
        shutil.rmtree(str(output_directory))


def _generate_pdoc_command_list(output_directory: Path,
                                module: str) -> List[str]:
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


def generate_docs(output_directory: Path, module: str) -> int:
    """Triggers building the documentation."""
    _clear_previous_docs(output_directory)
    logger.info("Creating Pdoc documentation.")
    try:
        command_list = _generate_pdoc_command_list(output_directory, module)
        check_call(command_list)
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
        default=configuration.get_value(
            ConfigurationVariable.DOCUMENTATION_DEFAULT_OUTPUT_PATH
        ),
    )
    args = parser.parse_args()
    output_directory = Path(args.output_directory)
    module = configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)
    sys.exit(generate_docs(output_directory=output_directory, module=module))


if __name__ == "__main__":
    main()
