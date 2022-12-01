#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Helpers for calculating hashes or UUID."""
import hashlib
import uuid
from pathlib import Path


def generate_uuid_based_on_str(string: str) -> str:
    """Generates a UUID based on a string.

    Args:
        string: string to base the UUID generation on

    Returns:
        a UUID
    """
    m = hashlib.md5()
    m.update((string if string else "").encode("utf-8"))
    return str(uuid.UUID(m.hexdigest()))


def determine_sha1_hash_of_file(filepath: Path) -> str:
    """Calculates the checksum of a file.

    Args:
        filepath: path to the file

    Returns:
        corresponding SHA1 hash.
    """
    if not filepath.exists() or not filepath.is_file():
        return "0"
    BLOCKSIZE = 65536
    hasher = hashlib.sha1()
    with open(str(filepath), "rb") as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    return hasher.hexdigest()
