#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Easy news files generation.

Usage:
    create-news-file "Fixed a bug" --type bugfix
"""
import argparse
import logging

import sys

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.assert_news import validate_news_file
from continuous_delivery_scripts.utils.logging import log_exception
from continuous_delivery_scripts.utils.news_file import NewsType, create_news_file

logger = logging.getLogger(__name__)

NEWS_DIR = configuration.get_value(ConfigurationVariable.NEWS_DIR)


def main() -> int:
    """Parses cli arguments and creates a news file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("news_text", help="Contents of the news file.")
    parser.add_argument(
        "-t", "--type", help="News type to create.", choices=[t.name for t in NewsType], default="feature"
    )

    args = parser.parse_args()
    created_file = create_news_file(str(NEWS_DIR), args.news_text, NewsType[args.type])

    try:
        validate_news_file(created_file)
    except ValueError as e:
        created_file.unlink()
        log_exception(logger, e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
