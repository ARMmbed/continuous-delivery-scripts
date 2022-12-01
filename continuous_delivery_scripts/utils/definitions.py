#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Place to store generic project concepts for the ci scripts."""
import enum
from typing import List

UNKNOWN = "unknown"


class CommitType(enum.Enum):
    """Type of commits."""

    DEVELOPMENT = 1
    BETA = 2
    RELEASE = 3

    @staticmethod
    def choices() -> List[str]:
        """Gets a list of all possible commit types.

        Returns:
            a list of commit types
        """
        return [t.name.lower() for t in CommitType]

    @staticmethod
    def parse(type_str: str) -> "CommitType":
        """Determines the commit type from a string.

        Args:
            type_str: string to parse.

        Returns:
            corresponding commit type.
        """
        try:
            return CommitType[type_str.upper()]
        except KeyError as e:
            raise ValueError(f"Unknown commit type: {type_str}. {e}")
