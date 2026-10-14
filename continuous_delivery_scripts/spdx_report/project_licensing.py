#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Project-level licence fetching, validation, and obligations reporting.

References:
- SPDX licence list and JSON details: https://spdx.org/licenses/
- SPDX licence expression guidance: https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/
- SPDX matching guidance: https://spdx.github.io/spdx-spec/v2.3/license-matching-guidelines-and-templates/
- ScanCode LicenseDB: https://scancode-licensedb.aboutcode.org/
- GitHub licences API: https://docs.github.com/en/rest/licenses/licenses
- choosealicense.com: https://choosealicense.com/
- OSADL licence obligations checklists: https://www.osadl.org/License-Checklists.oss-compliance-lists.0.html
"""

import html
import json
import jinja2
import logging
import re
from difflib import unified_diff
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from continuous_delivery_scripts.spdx_report.scancode_licence_db import ScanCodeLicenceDB
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.third_party_licences import (
    LICENSE_REF_PROPRIETARY,
    OPENSOURCE_LICENCES,
    is_proprietary_licence,
    normalise_proprietary_licence,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
MAX_RESPONSE_SIZE = 4 * 1024 * 1024
USER_AGENT = "continuous-delivery-scripts"
SCANCODE_DB = ScanCodeLicenceDB()
JINJA_TEMPLATE_LICENCE_OBLIGATIONS_TEXT = "licence_obligations_report.txt.jinja2"
SCANCODE_TEXT_KEY = "text"
SPDX_NAME_KEY = "name"
SPDX_IS_OSI_APPROVED_KEY = "isOsiApproved"
SPDX_LICENSE_TEXT_KEY = "licenseText"
GITHUB_BODY_KEY = "body"


@dataclass(frozen=True)
class RetrievedProjectLicenceText:
    """Text fetched for a project licence file from a public source.

    The text may come from ScanCode LicenseDB, SPDX.org, the GitHub licences
    API, or choosealicense.com.
    """

    identifier: str
    text: str
    source: str
    url: str


@dataclass(frozen=True)
class ChooseALicenseMetadata:
    """Summary information exposed by choosealicense.com.

    Reference: https://choosealicense.com/
    """

    summary: Optional[str]
    permissions: tuple[str, ...]
    conditions: tuple[str, ...]
    limitations: tuple[str, ...]
    text: Optional[str]
    url: Optional[str]


def get_project_licence_identifier(identifier: Optional[str] = None) -> str:
    """Return the project's single SPDX licence identifier.

    This helper accepts one exact SPDX identifier only. Compound expressions are
    intentionally rejected for commands whose output assumes one canonical text
    or one obligations profile.

    References:
    - https://spdx.org/licenses/
    - https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/
    """
    raw_identifier: str = identifier or str(configuration.get_value(ConfigurationVariable.FILE_LICENCE_IDENTIFIER))
    normalised_identifier: str = normalise_proprietary_licence(raw_identifier.strip())
    if is_proprietary_licence(raw_identifier):
        return normalised_identifier
    if not has_single_project_licence_identifier(raw_identifier):
        raise ValueError(
            "This command only covers one exact SPDX licence identifier and does not cover "
            "compound licence expressions such as AND, OR, or WITH."
        )
    licence = OPENSOURCE_LICENCES.get_licence(normalised_identifier, allow_fuzzy=False)
    if not licence or licence.identifier != normalised_identifier:
        raise ValueError(f"'{normalised_identifier}' is not a recognised SPDX licence identifier.")
    return normalised_identifier


def has_single_project_licence_identifier(identifier: Optional[str] = None) -> bool:
    """Return whether the configured project licence is one exact identifier.

    This excludes compound SPDX expressions such as ``AND``, ``OR``, and
    ``WITH`` because the project-level licence-file and obligations workflows
    in this module only cover one canonical licence at a time.
    """
    raw_identifier: str = identifier or str(configuration.get_value(ConfigurationVariable.FILE_LICENCE_IDENTIFIER))
    normalised_identifier: str = normalise_proprietary_licence(raw_identifier.strip())
    if is_proprietary_licence(raw_identifier):
        return True
    return not any(token in normalised_identifier for token in (" AND ", " OR ", " WITH ", "(", ")"))


def get_project_licence_file_path() -> Path:
    """Resolve the configured path of the project licence file.

    The default configuration is ``LICENSE`` at the project root.
    """
    configured_path = Path(str(configuration.get_value(ConfigurationVariable.LICENCE_FILE_PATH)).strip())
    if configured_path.is_absolute():
        return configured_path
    return Path(str(configuration.get_value(ConfigurationVariable.PROJECT_ROOT))).joinpath(configured_path)


def normalise_licence_text(text: str) -> str:
    """Normalise licence text while preserving meaningful formatting.

    This is a lightweight normalization step used before comparison against
    canonical public licence texts. It is intentionally simpler than the full
    SPDX matching guidelines.

    Reference:
    - https://spdx.github.io/spdx-spec/v2.3/license-matching-guidelines-and-templates/
    """
    lines = [line.rstrip() for line in html.unescape(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def fetch_project_licence_text(identifier: str) -> Optional[RetrievedProjectLicenceText]:
    """Fetch canonical licence text for one SPDX identifier from public sources.

    Source order:
    1. ScanCode LicenseDB
    2. SPDX.org
    3. GitHub licences API
    4. choosealicense.com
    """
    for fetcher in (
        _fetch_scancode_licence_text,
        _fetch_spdx_licence_text,
        _fetch_github_licence_text,
        _fetch_choosealicense_licence_text,
    ):
        try:
            result = fetcher(identifier)
        except Exception as error:
            logger.debug("Could not fetch %s from %s: %s", identifier, fetcher.__name__, error)
            continue
        if result and result.text.strip():
            return result
    return None


def fetch_spdx_licence_details(identifier: str) -> Optional[Dict[str, object]]:
    """Fetch SPDX licence metadata for one identifier.

    Reference: https://spdx.org/licenses/
    """
    try:
        return _read_json(f"https://spdx.org/licenses/{identifier}.json")
    except Exception as error:
        logger.debug("SPDX licence details unavailable for %s: %s", identifier, error)
        return None


def fetch_osadl_obligations(identifier: str) -> Optional[str]:
    """Fetch the OSADL checklist text for one identifier when available.

    Reference: https://www.osadl.org/License-Checklists.oss-compliance-lists.0.html
    """
    try:
        return normalise_licence_text(
            _read_text(f"https://www.osadl.org/fileadmin/checklists/unreflicenses/{identifier}.txt")
        )
    except Exception as error:
        logger.debug("OSADL obligations unavailable for %s: %s", identifier, error)
        return None


def fetch_choosealicense_metadata(identifier: str) -> Optional[ChooseALicenseMetadata]:
    """Fetch descriptive choosealicense.com metadata when supported.

    This is used for the user-facing permissions/conditions/limitations summary.

    Reference: https://choosealicense.com/
    """
    for slug in _choosealicense_slugs(identifier):
        url = f"https://choosealicense.com/licenses/{slug}/"
        try:
            page = _read_text(url)
            return ChooseALicenseMetadata(
                summary=_extract_choosealicense_summary(page),
                permissions=tuple(_extract_choosealicense_list(page, "license-permissions")),
                conditions=tuple(_extract_choosealicense_list(page, "license-conditions")),
                limitations=tuple(_extract_choosealicense_list(page, "license-limitations")),
                text=_extract_choosealicense_text(page),
                url=url,
            )
        except Exception as error:
            logger.debug("choosealicense.com metadata unavailable for %s at %s: %s", identifier, url, error)
    return None


def ensure_project_licence_file_conforms(create_if_missing: bool, update_if_mismatched: bool = False) -> Path:
    """Ensure the configured project licence file exists and matches the configured SPDX identifier.

    For non-proprietary single-identifier projects, the file content is checked
    against canonical public licence text fetched from the supported services.
    For proprietary projects, this helper only verifies presence because CDS has
    no public canonical reference text to compare against.
    """
    identifier = get_project_licence_identifier()
    licence_file = get_project_licence_file_path()
    if is_proprietary_licence(identifier):
        if licence_file.exists() and licence_file.is_file():
            return licence_file
        raise ValueError(f"The project uses a proprietary licence. The author must provide {licence_file} manually.")
    fetched = fetch_project_licence_text(identifier)
    if not fetched:
        raise ValueError(
            f"Could not fetch licence text for {identifier} from ScanCode LicenseDB, SPDX.org, "
            "GitHub API, or choosealicense.com."
        )
    if licence_file.exists():
        if not licence_file.is_file():
            raise ValueError(f"Configured licence path exists but is not a file: {licence_file}")
        actual_text = licence_file.read_text(encoding="utf8")
        if _normalise_licence_text_for_comparison(actual_text) != _normalise_licence_text_for_comparison(fetched.text):
            _log_licence_text_diff(actual_text, fetched.text, licence_file, fetched.source)
            if update_if_mismatched:
                licence_file.write_text(fetched.text.rstrip() + "\n", encoding="utf8")
                print(f"Updated {licence_file} from {fetched.source}: {fetched.url}")
                return licence_file
            raise ValueError(f"Configured SPDX identifier {identifier} does not match the contents of {licence_file}.")
        return licence_file
    if not create_if_missing:
        raise ValueError(f"Configured SPDX identifier {identifier} requires a project licence file at {licence_file}.")
    licence_file.parent.mkdir(parents=True, exist_ok=True)
    licence_file.write_text(fetched.text.rstrip() + "\n", encoding="utf8")
    print(f"Created {licence_file} from {fetched.source}: {fetched.url}")
    return licence_file


def sync_project_licence_file() -> Path:
    """Create the configured project licence file when it is missing.

    This workflow only supports projects configured with one exact SPDX licence
    identifier.
    """
    return ensure_project_licence_file_conforms(create_if_missing=True, update_if_mismatched=True)


def describe_licence_obligations(identifier: Optional[str] = None) -> str:
    """Return a human-readable obligations summary for one project licence.

    The rendered report combines:
    - SPDX.org licence metadata
    - choosealicense.com summary data
    - OSADL obligations text

    This workflow only supports projects configured with one exact SPDX licence
    identifier.
    """
    resolved_identifier = get_project_licence_identifier(identifier)
    if is_proprietary_licence(resolved_identifier):
        return _render_licence_obligations_report(
            {
                "identifier": LICENSE_REF_PROPRIETARY,
                "name": None,
                "is_osi_approved": None,
                "summary": None,
                "permissions": (),
                "conditions": (),
                "limitations": (),
                "osadl_obligations": None,
                "is_proprietary": True,
            }
        )

    spdx_details = fetch_spdx_licence_details(resolved_identifier) or {}
    choosealicense = fetch_choosealicense_metadata(resolved_identifier)
    osadl = fetch_osadl_obligations(resolved_identifier)
    return _render_licence_obligations_report(
        {
            "identifier": resolved_identifier,
            "name": spdx_details.get(SPDX_NAME_KEY) if isinstance(spdx_details.get(SPDX_NAME_KEY), str) else None,
            "is_osi_approved": (
                "yes"
                if spdx_details.get(SPDX_IS_OSI_APPROVED_KEY) is True
                else "no" if spdx_details.get(SPDX_IS_OSI_APPROVED_KEY) is False else None
            ),
            "summary": choosealicense.summary if choosealicense else None,
            "permissions": choosealicense.permissions if choosealicense else (),
            "conditions": choosealicense.conditions if choosealicense else (),
            "limitations": choosealicense.limitations if choosealicense else (),
            "osadl_obligations": osadl.splitlines() if osadl else None,
            "is_proprietary": False,
        }
    )


def _normalise_licence_text_for_comparison(text: str) -> str:
    return re.sub(r"\s+", " ", normalise_licence_text(text)).strip()


def _log_licence_text_diff(actual_text: str, expected_text: str, licence_file: Path, source: str) -> None:
    diff = "\n".join(
        unified_diff(
            normalise_licence_text(actual_text).splitlines(),
            normalise_licence_text(expected_text).splitlines(),
            fromfile=str(licence_file),
            tofile=f"canonical ({source})",
            lineterm="",
        )
    )
    if diff:
        logger.warning("Project licence file differs from canonical text:\n%s", diff)


def _fetch_scancode_licence_text(identifier: str) -> Optional[RetrievedProjectLicenceText]:
    info = SCANCODE_DB.find(identifier)
    if not info:
        return None
    data = _read_json(info.url)
    text = data.get(SCANCODE_TEXT_KEY)
    if not isinstance(text, str) or not text.strip():
        return None
    return RetrievedProjectLicenceText(
        identifier=identifier,
        text=normalise_licence_text(text),
        source="ScanCode LicenseDB",
        url=info.url,
    )


def _fetch_spdx_licence_text(identifier: str) -> Optional[RetrievedProjectLicenceText]:
    url = f"https://spdx.org/licenses/{identifier}.json"
    data = _read_json(url)
    text = data.get(SPDX_LICENSE_TEXT_KEY)
    if not isinstance(text, str) or not text.strip():
        return None
    return RetrievedProjectLicenceText(
        identifier=identifier,
        text=normalise_licence_text(text),
        source="SPDX.org",
        url=url,
    )


def _fetch_github_licence_text(identifier: str) -> Optional[RetrievedProjectLicenceText]:
    for slug in _github_api_slugs(identifier):
        url = f"https://api.github.com/licenses/{slug}"
        data = _read_json(url, headers={"Accept": "application/vnd.github+json"})
        text = data.get(GITHUB_BODY_KEY)
        if not isinstance(text, str) or not text.strip():
            continue
        return RetrievedProjectLicenceText(
            identifier=identifier,
            text=normalise_licence_text(text),
            source="GitHub API",
            url=url,
        )
    return None


def _fetch_choosealicense_licence_text(identifier: str) -> Optional[RetrievedProjectLicenceText]:
    metadata = fetch_choosealicense_metadata(identifier)
    if not metadata or not metadata.text or not metadata.url:
        return None
    return RetrievedProjectLicenceText(
        identifier=identifier,
        text=normalise_licence_text(metadata.text),
        source="choosealicense.com",
        url=metadata.url,
    )


def _github_api_slugs(identifier: str) -> Iterable[str]:
    yield identifier.lower()
    simplified = re.sub(r"-(?:only|or-later)$", "", identifier, flags=re.IGNORECASE).lower()
    if simplified != identifier.lower():
        yield simplified


def _choosealicense_slugs(identifier: str) -> Iterable[str]:
    yield from _github_api_slugs(identifier)


def _read_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = response.read(MAX_RESPONSE_SIZE + 1)
    if len(payload) > MAX_RESPONSE_SIZE:
        raise ValueError(f"Response from {url} exceeds the maximum supported size")
    return cast(str, payload.decode("utf8"))


def _read_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    try:
        data = json.loads(_read_text(url, headers=headers))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not retrieve JSON from {url}: {error}")
    if not isinstance(data, dict):
        raise ValueError(f"JSON payload from {url} is not an object")
    return data


def _extract_choosealicense_summary(page: str) -> Optional[str]:
    match = re.search(r'<div class="license-body">.*?<p>\s*(.*?)\s*</p>', page, flags=re.DOTALL)
    return _strip_html(match.group(1)) if match else None


def _extract_choosealicense_list(page: str, class_name: str) -> list[str]:
    block = re.search(rf'<ul class="{class_name}">(.*?)</ul>', page, flags=re.DOTALL)
    if not block:
        return []
    items = []
    for entry in re.findall(r"<li[^>]*>(.*?)</li>", block.group(1), flags=re.DOTALL):
        text = _strip_html(entry)
        if text:
            items.append(text)
    return items


def _extract_choosealicense_text(page: str) -> Optional[str]:
    match = re.search(r'<pre id="license-text"[^>]*>(.*?)</pre>', page, flags=re.DOTALL)
    return normalise_licence_text(match.group(1)) if match else None


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", text).strip()


def _get_report_jinja2_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(Path(__file__).resolve().parent.joinpath("templates"))),
        autoescape=lambda name: bool(name and name.endswith(".html.jinja2")),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_licence_obligations_report(arguments: Dict[str, object]) -> str:
    template = _get_report_jinja2_env().get_template(JINJA_TEMPLATE_LICENCE_OBLIGATIONS_TEXT)
    return cast(str, template.render(**arguments))
