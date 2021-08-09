#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers with regards to news files."""
import enum
import pathlib
from datetime import datetime


class NewsType(enum.Enum):
    """Describes the type of news we're writing."""

    bugfix = 0
    doc = 1
    feature = 2
    major = 3
    misc = 4
    removal = 5


def create_news_file(news_dir: str, news_text: str, news_type: NewsType) -> pathlib.Path:
    """Facilitates creating a news file, determining it's file name based on the type."""
    file_path = determine_news_file_path(news_dir, news_type)
    _write_file(file_path, news_text)
    return file_path


def determine_news_file_path(news_dir: str, news_type: NewsType) -> pathlib.Path:
    """Returns an available file path for given news type."""
    news_file_name = _determine_todays_news_file_name()
    news_file_path = pathlib.Path(news_dir, f"{news_file_name}.{news_type.name}")
    inc = 0
    while news_file_path.exists():
        inc += 1
        news_file_path = news_file_path.with_name(f"{news_file_name}{inc:0=2}.{news_type.name}")
    return news_file_path


def _write_file(file_path: pathlib.Path, text: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text = f"{text}\n"
    file_path.write_text(text)


def _determine_todays_news_file_name() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")
