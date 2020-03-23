#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Easy news files generation.

Usage:
    create-news-file "Fixed a bug" --type bugfix
"""
import argparse
import enum
import logging
import pathlib
import sys
from datetime import datetime

from mbed_tools_ci_scripts.utils.configuration import configuration, ConfigurationVariable
from mbed_tools_ci_scripts.assert_news import validate_news_file
from mbed_tools_ci_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


NEWS_DIR = configuration.get_value(ConfigurationVariable.NEWS_DIR)


class NewsType(enum.Enum):
    """Describes the type of news we're writing."""

    bugfix = 0
    doc = 1
    feature = 2
    major = 3
    misc = 4
    removal = 5


def create_news_file(news_text: str, news_type: NewsType) -> pathlib.Path:
    """Facilitates creating a news file, determining it's file name based on the type."""
    file_path = determine_news_file_path(news_type)
    _write_file(file_path, news_text)
    return file_path


def determine_news_file_path(news_type: NewsType) -> pathlib.Path:
    """Returns an available file path for given news type."""
    news_file_name = _determine_todays_news_file_name()
    news_file_path = pathlib.Path(NEWS_DIR, f"{news_file_name}.{news_type.name}")
    inc = 0
    while news_file_path.exists():
        inc += 1
        news_file_path = news_file_path.with_name(f"{news_file_name}{inc:0=2}.{news_type.name}")
    return news_file_path


def _write_file(file_path: pathlib.Path, text: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text)


def _determine_todays_news_file_name() -> str:
    return datetime.now().strftime("%Y%m%d")


def main() -> int:
    """Parses cli arguments and creates a news file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("news_text", help="Contents of the news file.")
    parser.add_argument("--type", help="News type to create.", choices=[t.name for t in NewsType], default="feature")

    args = parser.parse_args()
    created_file = create_news_file(args.news_text, NewsType[args.type])

    try:
        validate_news_file(created_file)
    except ValueError as e:
        created_file.unlink()
        log_exception(logger, e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
