#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Third party licences."""
import re

import json
from dataclasses import dataclass
from license_expression import Licensing, LicenseExpression, OR
from spdx.config import _licenses
from typing import Iterable, cast, Optional, Iterator, List, Pattern, Any

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.string_helpers import determine_similar_string_from_list


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
    if cleansed_descriptor in ["Apache Software License", "Apache", "apache"]:
        return "Apache-2.0"
    if cleansed_descriptor in ["LGPL", "UNKNOWN", "Dual License"]:
        # It is not possible to find which is the actual licence to consider.
        return UNKNOWN_LICENCE.identifier
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

    def load(self) -> None:
        """Loads licence data from internal Json file."""
        if self._licence_list and self._licence_store:
            return
        self._licence_store = {UNKNOWN_LICENCE.identifier: UNKNOWN_LICENCE}
        self._licence_list = [UNKNOWN_LICENCE.identifier]
        with open(_licenses, "r", encoding="utf8") as f:
            for licence in iter_licenses(json.load(f)):
                self._licence_store[licence.identifier] = licence
                self._licence_list.append(licence.identifier)
                self._licence_store[licence.name] = licence
                self._licence_list.append(licence.name)

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
        likelihood, licence = determine_similar_string_from_list(cleansed_descriptor, self._licence_list)
        return self._licence_store.get(licence) if likelihood > LICENCE_LIKELIHOOD_THRESHOLD else None


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


def _retrieve_licences_from_identifier_list(identifiers: Iterable[str]) -> Iterable[Licence]:
    for desc in identifiers:
        if "*" in desc:
            yield from _iter_matching_licences_from_pattern(desc)
        else:
            yield from _iter_matching_licences(desc)


def determine_allowed_opensource_licences_from_string(allowed_licences: Any) -> Iterable[Licence]:
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
