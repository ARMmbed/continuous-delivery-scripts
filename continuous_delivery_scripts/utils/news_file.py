#
# Copyright (C) 2020-2021 Arm. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers with regards to news files."""
import enum


class NewsType(enum.Enum):
    """Describes the type of news we're writing."""

    bugfix = 0
    doc = 1
    feature = 2
    major = 3
    misc = 4
    removal = 5
