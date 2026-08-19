#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Third party licences."""

import re

import json
from dataclasses import dataclass
from importlib.util import find_spec
from license_expression import Licensing, LicenseExpression, OR, get_spdx_licensing
from pathlib import Path
from typing import Dict, Iterable, cast, Optional, Iterator, List, Pattern, Any, Tuple

from continuous_delivery_scripts.utils.configuration import (
    ConfigurationVariable,
    configuration,
)
from continuous_delivery_scripts.utils.string_helpers import (
    determine_similar_string_from_list,
)


@dataclass(order=True, frozen=True)
class Licence:
    """Licence descriptor.

    Maps to what is defined in licenses.json in
    https://github.com/spdx/license-list-data/blob/master/json/licenses.json
    """

    reference_number: str
    identifier: str
    name: str
    is_deprecated: bool
    is_osi_approved: bool
    url: str
    reference: str


UNKNOWN_LICENCE = Licence(
    reference_number="Unknown",
    identifier="Unknown",
    name="Unknown",
    is_deprecated=True,
    is_osi_approved=False,
    url="Unknown",
    reference="Unknown",
)

LICENCE_LIKELIHOOD_THRESHOLD = 0.5

LICENCE_NON_ACCEPTED_CHARACTERS = r"[^\w\s\.\:\-()]"


def _get_spdx_licenses_path() -> Path:
    spec = find_spec("spdx")
    if not spec or not spec.origin:
        raise FileNotFoundError("Could not find SPDX licenses.json")
    return Path(spec.origin).resolve().parent.joinpath("licenses.json")


FALLBACK_LICENCE_DATA = {
    "0BSD": {
        "reference_number": "319",
        "name": "BSD Zero Clause License",
    },
    "Apache-2.0": {
        "reference_number": "26",
        "name": "Apache License 2.0",
    },
    "GPL-3.0-only": {
        "name": "GNU General Public License v3.0 only",
    },
    "MPL-2.0": {
        "name": "Mozilla Public License 2.0",
    },
    "MIT": {
        "name": "MIT License",
    },
    "PSF-2.0": {
        "name": "Python Software Foundation License 2.0",
    },
    "Python-2.0": {
        "name": "Python License 2.0",
    },
}


FALLBACK_LICENCE_ALIASES = {
    "0BSD": ["BSD", "BSD License", "BSD Zero Clause License"],
    "Apache-2.0": [
        "Apache",
        "Apache 2",
        "Apache 2.0",
        "Apache License 2",
        "Apache License 2.0",
        "Apache License Version 2",
        "Apache License Version 2.0",
        "Apache License, Version 2",
        "Apache License, Version 2.0",
        "Apache Licence 2",
        "Apache Licence 2.0",
        "Apache Licence Version 2",
        "Apache Licence Version 2.0",
        "Apache Licence, Version 2",
        "Apache Licence, Version 2.0",
        "Apache Software License",
    ],
    "GPL-3.0-only": ["GPL 3", "GPL 3.0", "GPL-3.0", "GPL-3", "GNU GPL 3"],
    "MIT": ["MIT License"],
    "PSF-2.0": ["Python Software Foundation License 2.0"],
    "Python-2.0": ["Python Software Foundation License"],
}


def _build_fallback_licence(identifier: str, is_deprecated: bool = False) -> Licence:
    metadata = FALLBACK_LICENCE_DATA.get(identifier, {})
    return Licence(
        reference_number=str(metadata.get("reference_number", "")),
        identifier=identifier,
        name=str(metadata.get("name", identifier)),
        is_deprecated=is_deprecated,
        is_osi_approved=bool(metadata.get("is_osi_approved", True)),
        url=f"http://spdx.org/licenses/{identifier}.json",
        reference=f"./{identifier}.html",
    )


def _iter_fallback_licences() -> Iterable[Tuple[Licence, Iterable[str]]]:
    spdx_licensing = get_spdx_licensing()
    seen = set()
    for symbol in spdx_licensing.known_symbols.values():
        identifier = getattr(symbol, "key", None)
        if not identifier or identifier in seen:
            continue
        if identifier.startswith("LicenseRef-") or getattr(symbol, "is_exception", False):
            continue
        seen.add(identifier)
        aliases = list(getattr(symbol, "aliases", ())) + FALLBACK_LICENCE_ALIASES.get(identifier, [])
        yield _build_fallback_licence(identifier, is_deprecated=bool(getattr(symbol, "is_deprecated", False))), aliases


def _normalise_licence_text(text: str) -> str:
    normalised_text = text.strip().lower()
    normalised_text = re.sub(r"osi\s?approved[:]*", "", normalised_text)
    normalised_text = re.sub(r"licen[cs]e", " ", normalised_text)
    normalised_text = re.sub(r"version", " ", normalised_text)
    normalised_text = re.sub(r"[^\w\s]", " ", normalised_text)
    normalised_text = re.sub(r"\s+", " ", normalised_text)
    return normalised_text.strip()


def _parse_licence_expression(licensing: Licensing, licence_expression: str) -> LicenseExpression:
    # Removing any unwanted characters so that the expression follows the laws:
    # > the valid characters are: letters and numbers, underscore, dot, colon or hyphen signs and spaces
    expression = re.sub(LICENCE_NON_ACCEPTED_CHARACTERS, "", licence_expression)
    expression = re.sub(r"\([sS]ee [\w\s\.\-]*\)", "", expression)
    return licensing.parse(expression)


def parse_licence(licence_info: dict) -> Licence:
    """Parses a licence entry in the Json file and translates it into a licence object."""
    return Licence(
        reference_number=licence_info.get("referenceNumber", ""),
        identifier=licence_info.get("licenseId", ""),
        name=licence_info.get("name", ""),
        url=licence_info.get("detailsUrl", ""),
        reference=licence_info.get("reference", ""),
        is_deprecated=bool(licence_info.get("isDeprecatedLicenseId", False)),
        is_osi_approved=bool(licence_info.get("isOsiApproved", True)),
    )


def iter_licenses(licence_info: dict) -> Iterable[Licence]:
    """Gets a generator over all the licences present in licenses.json."""
    licences = cast(Iterable[dict], licence_info.get("licenses", []))
    for licence_info in licences:
        yield parse_licence(licence_info)


def _handle_special_licence_entries(cleansed_descriptor: str) -> str:
    if cleansed_descriptor in ["Python Software Foundation License"]:
        return "Python"
    if re.fullmatch(r"Python(?:[\w\s\-\.]*)", cleansed_descriptor, re.IGNORECASE):
        return "Python-2.0"
    if cleansed_descriptor in ["Apache Software License", "Apache", "apache"]:
        return "Apache-2.0"
    if cleansed_descriptor in ["LGPL", "UNKNOWN", "Dual License"]:
        # It is not possible to find which is the actual licence to consider.
        return UNKNOWN_LICENCE.identifier
    if re.fullmatch(r"Apache(?:\s+(?:Software\s+)?)?(?:Licen[cs]e)?(?:,?\s+Version)?\s*2(?:\.0)?", cleansed_descriptor):
        return "Apache-2.0"
    if re.fullmatch(r"GPL\s*3(?:\.0)?", cleansed_descriptor, re.IGNORECASE):
        return "GPL-3.0-only"
    return cleansed_descriptor


def cleanse_licence_descriptor(licence_descriptor: str) -> str:
    """Cleanses the licence descriptor to only keep words describing the licence."""
    cleansed_descriptor = licence_descriptor.strip()
    cleansed_descriptor = re.sub(r"OSI\s?[Aa]pproved[\:]*", "", cleansed_descriptor)
    cleansed_descriptor = re.sub(r"[pP]ublic [dD]omain", "", cleansed_descriptor)
    cleansed_descriptor = re.sub(r"BSD[-\s][Ll]ike", "BSD", cleansed_descriptor)
    cleansed_descriptor = re.sub(r"BSD [lL]icen[sc]e", "BSD", cleansed_descriptor)
    cleansed_descriptor = re.sub(r"MIT [lL]icen[sc]e", "MIT", cleansed_descriptor)
    cleansed_descriptor = _handle_special_licence_entries(cleansed_descriptor.strip())
    if cleansed_descriptor.lower().startswith("the"):
        cleansed_descriptor = cleansed_descriptor[3:].strip()
    return cleansed_descriptor


class OpenSourceLicences:
    """All the opensource licences known."""

    def __init__(self) -> None:
        """Initialiser."""
        self._licence_store: Optional[dict] = None
        self._licence_list: Optional[list] = None

    def _store_licence(self, licence: Licence, aliases: Iterable[str] = ()) -> None:
        if not self._licence_store or self._licence_list is None:
            return
        entries = [licence.identifier, licence.name, *aliases]
        for entry in entries:
            if not entry:
                continue
            self._licence_store[entry] = licence
            self._licence_list.append(entry)

    def load(self) -> None:
        """Loads licence data from internal Json file."""
        if self._licence_list and self._licence_store:
            return
        self._licence_store = {UNKNOWN_LICENCE.identifier: UNKNOWN_LICENCE}
        self._licence_list = [UNKNOWN_LICENCE.identifier]
        try:
            with open(_get_spdx_licenses_path(), "r", encoding="utf8") as f:
                for licence in iter_licenses(json.load(f)):
                    self._store_licence(licence)
            return
        except (FileNotFoundError, ModuleNotFoundError):
            pass

        for licence, aliases in _iter_fallback_licences():
            self._store_licence(licence, aliases)

    def get_licences_from_pattern(self, licence_descriptor_pattern: Pattern) -> Optional[List[Licence]]:
        """Determines all the licences following a certain pattern."""
        self.load()
        if not self._licence_store or not self._licence_list:
            return None
        matching_licences = [licence for licence in self._licence_list if licence_descriptor_pattern.match(licence)]
        return (
            [cast(Licence, self._licence_store.get(licence)) for licence in matching_licences]
            if matching_licences
            else None
        )

    def get_licence(self, licence_descriptor: Optional[str]) -> Optional[Licence]:
        """Determines the licence based on a string descriptor e.g. Apache 2."""
        self.load()
        if not self._licence_store or not self._licence_list or not licence_descriptor:
            return None
        cleansed_descriptor = cleanse_licence_descriptor(licence_descriptor)
        exact_match = self._licence_store.get(cleansed_descriptor)
        if exact_match:
            return cast(Licence, exact_match)

        normalised_map: Dict[str, Licence] = {}
        for name in self._licence_list:
            licence = cast(Licence, self._licence_store.get(name))
            if licence:
                normalised_map[_normalise_licence_text(name)] = licence

        normalised_descriptor = _normalise_licence_text(cleansed_descriptor)
        normalised_exact_match = normalised_map.get(normalised_descriptor)
        if normalised_exact_match:
            return normalised_exact_match

        likelihood, matched_key = determine_similar_string_from_list(normalised_descriptor, normalised_map.keys())
        return normalised_map.get(matched_key) if likelihood > LICENCE_LIKELIHOOD_THRESHOLD else None


OPENSOURCE_LICENCES = OpenSourceLicences()


def cleanse_licence_expression(licence_expression: str) -> str:
    """Cleanses a licence expression by using SPDX identifiers when possible.

    A licence expression can be a combination of licences and in a lot of cases is free-form text.
    The idea is to return an equivalent expression but using SPDX identifiers when possible.
    """
    simplified_expression = _parse_licence_expression(Licensing(), licence_expression).simplify()
    for s in simplified_expression.symbols:
        corresponding_licence = OPENSOURCE_LICENCES.get_licence(s.key)
        if corresponding_licence:
            s.key = corresponding_licence.identifier
    return simplify_licence_expression(str(simplified_expression))


def _iter_matching_licences(desc: str) -> Iterable[Licence]:
    licence = OPENSOURCE_LICENCES.get_licence(desc)
    if licence:
        yield licence


def _iter_matching_licences_from_pattern(desc: str) -> Iterable[Licence]:
    desc_pattern = re.compile(desc.replace("*", ".*"), re.IGNORECASE)
    licences = OPENSOURCE_LICENCES.get_licences_from_pattern(desc_pattern)
    if licences:
        yield from licences


def _retrieve_licences_from_identifier_list(
    identifiers: Iterable[str],
) -> Iterable[Licence]:
    for desc in identifiers:
        if "*" in desc:
            yield from _iter_matching_licences_from_pattern(desc)
        else:
            yield from _iter_matching_licences(desc)


def determine_allowed_opensource_licences_from_string(
    allowed_licences: Any,
) -> Iterable[Licence]:
    """Determines all the third party licences allowed as set in the input parameter."""
    if isinstance(allowed_licences, str):
        allowed_licences = allowed_licences.split(", ")
    if isinstance(allowed_licences, (list, dict, tuple, set)):
        yield from _retrieve_licences_from_identifier_list(allowed_licences)


def get_allowed_opensource_licences() -> Iterable[Licence]:
    """Determines all the third party licences allowed for a given project."""
    yield from determine_allowed_opensource_licences_from_string(
        configuration.get_value(ConfigurationVariable.ACCEPTED_THIRD_PARTY_LICENCES)
    )


def simplify_licence_expression(licence_expression: str) -> str:
    """Simplifies a licence expression."""
    return str(_parse_licence_expression(Licensing(), licence_expression).simplify())


def determine_licence_compound(main_licence: str, additional_licences: List[str]) -> str:
    """Determines the overall licence based on main licence and additional licences."""
    overall_licence = f"({main_licence}) AND ({') AND ('.join(additional_licences)})"
    return str(_parse_licence_expression(Licensing(), overall_licence).simplify())


def determine_licences_not_in_list(licence_expression: str, licence_list: Iterator[str]) -> Iterator[str]:
    """Determines all the licences in an expression which are not in list."""
    licensing_util = Licensing()
    licence_keys = licensing_util.license_keys(_parse_licence_expression(licensing_util, licence_expression))
    for licence in licence_keys:
        if licence not in licence_list:
            yield licence


def determine_whether_licence_expression_is_compliant(licence_expression: str, licence_list: list) -> bool:
    """Checks whether an expression is compliant with a list of licences."""
    licensing_util = Licensing()
    for licence in licence_list:
        if licensing_util.contains(licence_expression, licence):
            return True
    return False


def _is_expression_or(licence_expression: str) -> bool:
    licensing_util = Licensing()
    return isinstance(_parse_licence_expression(licensing_util, licence_expression), OR)


def is_licence_accepted(licence_expression: str) -> bool:
    """Determines whether the licence expressed is valid with regards to project's accepted licences."""
    authorised_licences = [licence.identifier for licence in get_allowed_opensource_licences()]
    is_or = _is_expression_or(licence_expression)
    if bool([licence for licence in determine_licences_not_in_list(licence_expression, iter(authorised_licences))]):
        return (
            determine_whether_licence_expression_is_compliant(licence_expression, authorised_licences)
            if is_or
            else False
        )
    return True
