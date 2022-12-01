#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers with regards to news files."""
import enum
import pathlib
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class NewsType(enum.Enum):
    """Describes the type of news we're writing."""

    bugfix = 0
    doc = 1
    feature = 2
    major = 3
    misc = 4
    removal = 5


def create_news_file(news_dir: str, news_text: str, news_type: Any) -> pathlib.Path:
    """Facilitates creating a news file, determining its file name based on the type."""
    message_type = NewsType.misc
    if isinstance(news_type, str):
        message_type = NewsType[news_type]
    elif isinstance(news_type, NewsType):
        message_type = news_type
    file_path = determine_news_file_path(news_dir, message_type)
    _write_file(file_path, news_text)
    return file_path


def determine_news_file_path(news_dir: str, news_type: NewsType) -> pathlib.Path:
    """Returns an available file path for given news type."""
    news_file_name = determine_basic_new_news_file_name()
    news_file_path = pathlib.Path(news_dir, f"{news_file_name}.{news_type.name}")
    inc = 0
    while news_file_path.exists():
        inc += 1
        news_file_path = news_file_path.with_name(f"{news_file_name}{inc:0=2}.{news_type.name}")
    return news_file_path


def _write_file(file_path: pathlib.Path, text: str) -> None:
    logger.info(f"Writing news file: {file_path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text = f"{text}\n"
    file_path.write_text(text)


def determine_basic_new_news_file_name() -> str:
    """Returns a new news file name."""
    return datetime.now().strftime("%Y%m%d%H%M%S")
