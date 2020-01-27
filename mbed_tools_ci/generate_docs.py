"""Generates documentation using Pdoc."""
import argparse
import logging
import sys
from subprocess import check_call

from mbed_tools_ci.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci.utils.logging import log_exception

logger = logging.getLogger(__name__)


def generate_docs(output_directory: str) -> int:
    """Triggers building the documentation.

    Module to document and the output destination path
    can be set in the mbed_tools_ci.utils.definitions config file.
    """
    command_list = [
        "pdoc", "--html",
        f"{configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)}",
        "--output-dir",
        f'{output_directory}', "--force", "--config",
        "show_type_annotations=True"
    ]

    logger.info('Creating Pdoc documentation.')

    try:
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
            ConfigurationVariable.DOCUMENTATION_DEFAULT_OUTPUT_PATH),
    )
    args = parser.parse_args()
    sys.exit(generate_docs(output_directory=args.output_directory))


if __name__ == '__main__':
    main()
