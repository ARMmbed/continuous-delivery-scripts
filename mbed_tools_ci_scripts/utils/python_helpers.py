#
# Copyright (c) 2020, Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities around python language."""


def flatten_dictionary(dictionary: dict) -> list:
    """Flattens a dictionary and transforms it into a list [key, value, ...]."""
    return [item for pair in dictionary.items() for item in pair]
