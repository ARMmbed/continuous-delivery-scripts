#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Optional exact SPDX-identifier lookups in ScanCode LicenseDB."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.request import urlopen

INDEX_URL = "https://scancode-licensedb.aboutcode.org/index.json"
BASE_URL = "https://scancode-licensedb.aboutcode.org/"
MAX_INDEX_SIZE = 8 * 1024 * 1024
REQUEST_TIMEOUT = 5

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanCodeLicenceInfo:
    """A category and source URL from the public LicenseDB index."""

    identifier: str
    category: str
    url: str


class ScanCodeLicenceDB:
    """Fetch the index at most once, and never infer a licence from a name."""

    def __init__(self) -> None:
        """Defer the network request until an identifier is missing a rule."""
        self._index: Optional[Dict[str, ScanCodeLicenceInfo]] = None

    def find(self, identifier: str) -> Optional[ScanCodeLicenceInfo]:
        """Return metadata for one exact SPDX-listed licence identifier, if present."""
        if not identifier or identifier.startswith("LicenseRef-"):
            return None
        if self._index is None:
            self._index = self._fetch_index()
        return self._index.get(identifier)

    def _fetch_index(self) -> Dict[str, ScanCodeLicenceInfo]:
        try:
            with urlopen(INDEX_URL, timeout=REQUEST_TIMEOUT) as response:
                payload = response.read(MAX_INDEX_SIZE + 1)
            if len(payload) > MAX_INDEX_SIZE:
                raise ValueError("LicenseDB index exceeds the maximum response size")
            entries = json.loads(payload.decode("utf8"))
            if not isinstance(entries, list):
                raise ValueError("LicenseDB index is not a list")
            index = {}
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("is_exception") or entry.get("is_deprecated"):
                    continue
                identifier, category, filename = (
                    entry.get("spdx_license_key"),
                    entry.get("category"),
                    entry.get("json"),
                )
                if (
                    isinstance(identifier, str)
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", identifier)
                    and not identifier.startswith("LicenseRef-")
                    and isinstance(category, str)
                    and isinstance(filename, str)
                    and re.fullmatch(r"[a-z0-9][a-z0-9_.-]*\.json", filename)
                ):
                    index[identifier] = ScanCodeLicenceInfo(identifier, category, BASE_URL + filename)
            return index
        except (OSError, ValueError, UnicodeError) as error:
            logger.warning("ScanCode LicenseDB lookup unavailable: %s", error)
            return {}
