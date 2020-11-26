#
# Copyright (C) 2020 Arm Mbed. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities around python language."""


def flatten_dictionary(dictionary: dict) -> list:
    """Flattens a dictionary and transforms it into a list [key, value, ...]."""
    flat_list = list()
    for k, v in dictionary.items():
        flat_list.append(k)
        if isinstance(v, list):
            flat_list.extend(v)
        else:
            flat_list.append(v)
    return flat_list
