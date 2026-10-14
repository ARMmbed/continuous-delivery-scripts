#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Schema-based validation for ``[ProjectConfig]`` entries in ``pyproject.toml``."""

import re
import urllib.parse
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import toml

from continuous_delivery_scripts.language_specifics import all_language_plugins
from continuous_delivery_scripts.spdx_report.licence_assessment import LicenceAssessmentPolicy
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, FileConfig
from continuous_delivery_scripts.utils.news_file import NewsType
from continuous_delivery_scripts.utils.third_party_licences import simplify_licence_expression

Validator = Callable[[str, Any, Path], list[str]]


@dataclass(frozen=True)
class FieldSchema:
    """Validation rules for one ``ProjectConfig`` key."""

    validator: Validator


def validate_project_config(config_file: Optional[str] = None) -> list[str]:
    """Validate the project's ``[ProjectConfig]`` section against CDS' schema."""
    config_path = FileConfig._find_config_file(config_file)
    if not config_path:
        return ["Could not find pyproject.toml."]
    raw = toml.load(config_path)
    project_config = raw.get(FileConfig.CONFIG_SECTION)
    if project_config is None:
        return [f"{config_path}: missing [{FileConfig.CONFIG_SECTION}] section."]
    if not isinstance(project_config, dict):
        return [f"{config_path}: [{FileConfig.CONFIG_SECTION}] must be a TOML table."]

    project_dir = Path(config_path).resolve().parent
    errors = []
    known_keys = set(PROJECT_CONFIG_SCHEMA)
    for key in sorted(set(project_config) - known_keys):
        errors.append(f"Unknown ProjectConfig key: {key}")
    for key, schema in PROJECT_CONFIG_SCHEMA.items():
        if key not in project_config:
            continue
        errors.extend(schema.validator(key, project_config[key], project_dir))
    errors.extend(_validate_licence_assessment_policy(project_config, project_dir))
    return errors


def _validate_non_empty_string(key: str, value: Any, _project_dir: Path) -> list[str]:
    if isinstance(value, str) and value.strip():
        return []
    return [f"{key} must be a non-empty string."]


def _validate_boolean(key: str, value: Any, _project_dir: Path) -> list[str]:
    return [] if isinstance(value, bool) else [f"{key} must be true or false."]


def _validate_integer(key: str, value: Any, _project_dir: Path) -> list[str]:
    return [] if isinstance(value, int) and not isinstance(value, bool) else [f"{key} must be an integer."]


def _validate_regex(key: str, value: Any, _project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, _project_dir)
    if errors:
        return errors
    try:
        re.compile(value)
    except re.error as error:
        return [f"{key} is not a valid regular expression: {error}"]
    return []


def _validate_uuid(key: str, value: Any, _project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, _project_dir)
    if errors:
        return errors
    try:
        uuid.UUID(value)
    except ValueError:
        return [f"{key} must be a valid UUID string."]
    return []


def _validate_url(key: str, value: Any, _project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, _project_dir)
    if errors:
        return errors
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return [f"{key} must be an absolute http or https URL."]
    return []


def _validate_language(key: str, value: Any, project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, project_dir)
    if errors:
        return errors
    languages = sorted(all_language_plugins())
    return [] if value.lower().strip() in languages else [f"{key} must be one of: {', '.join(languages)}"]


def _validate_news_type(key: str, value: Any, project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, project_dir)
    if errors:
        return errors
    choices = {item.name for item in NewsType}
    return [] if value in choices else [f"{key} must be one of: {', '.join(sorted(choices))}"]


def _validate_licence_expression(key: str, value: Any, project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, project_dir)
    if errors:
        return errors
    try:
        simplify_licence_expression(value)
    except Exception as error:
        return [f"{key} is not a valid SPDX licence expression: {error}"]
    return []


def _validate_string_or_list_of_strings(key: str, value: Any, project_dir: Path) -> list[str]:
    if isinstance(value, str):
        return _validate_non_empty_string(key, value, project_dir)
    if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
        return []
    return [f"{key} must be a string or a list of non-empty strings."]


def _validate_checked_licences(key: str, value: Any, project_dir: Path) -> list[str]:
    if isinstance(value, str):
        return []
    if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
        return []
    if not isinstance(value, dict):
        return [f"{key} must be a string, a list of strings, or a table."]
    errors = []
    for package_name, entry in value.items():
        if not isinstance(package_name, str) or not package_name.strip():
            errors.append(f"{key} package names must be non-empty strings.")
            continue
        if isinstance(entry, str):
            continue
        if not isinstance(entry, dict) or set(entry) - {"licence", "reason"}:
            errors.append(f"{key}.{package_name} must be a string or a table with only 'licence' and 'reason'.")
            continue
        for nested_key, nested_value in entry.items():
            if not isinstance(nested_value, str) or not nested_value.strip():
                errors.append(f"{key}.{package_name}.{nested_key} must be a non-empty string.")
    return errors


def _validate_manual_reviews(key: str, value: Any, _project_dir: Path) -> list[str]:
    if not isinstance(value, dict):
        return [f"{key} must be a table of package names and review reasons."]
    errors = []
    for package_name, entry in value.items():
        if not isinstance(package_name, str) or not package_name.strip():
            errors.append(f"{key} package names must be non-empty strings.")
            continue
        if isinstance(entry, str):
            if not entry.strip():
                errors.append(f"{key}.{package_name} must not be empty.")
            continue
        if not isinstance(entry, dict) or set(entry) - {"reason", "licence", "version"}:
            errors.append(f"{key}.{package_name} has invalid fields.")
            continue
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{key}.{package_name}.reason must be a non-empty string.")
        licence = entry.get("licence")
        if licence is not None and _validate_licence_expression(f"{key}.{package_name}.licence", licence, _project_dir):
            errors.extend(_validate_licence_expression(f"{key}.{package_name}.licence", licence, _project_dir))
        version = entry.get("version")
        if version is not None and (not isinstance(version, str) or not version.strip()):
            errors.append(f"{key}.{package_name}.version must be a non-empty string.")
    return errors


def _validate_path_string(key: str, value: Any, project_dir: Path) -> list[str]:
    errors = _validate_non_empty_string(key, value, project_dir)
    if errors:
        return errors
    path = Path(value)
    if path.is_absolute():
        return []
    try:
        project_dir.joinpath(path)
    except Exception as error:
        return [f"{key} is not a usable path: {error}"]
    return []


def _validate_licence_assessment_policy(project_config: dict, project_dir: Path) -> list[str]:
    if not any(
        key in project_config
        for key in (
            ConfigurationVariable.LICENCE_ASSESSMENT_RULES.name,
            ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH.name,
            ConfigurationVariable.LICENCE_ASSESSMENT_FAIL_ON.name,
        )
    ):
        return []
    try:
        resource = resources.files("continuous_delivery_scripts.spdx_report").joinpath(
            "data", "licence_assessment.toml"
        )
        default = toml.loads(resource.read_text(encoding="utf8"))
        override_path = project_config.get(ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH.name)
        override = toml.load(project_dir / override_path) if override_path else None
        inline_override = project_config.get(ConfigurationVariable.LICENCE_ASSESSMENT_RULES.name)
        policy = LicenceAssessmentPolicy(default, override, inline_override)
        fail_on = project_config.get(ConfigurationVariable.LICENCE_ASSESSMENT_FAIL_ON.name)
        if fail_on is not None:
            policy._set_fail_on(fail_on, "ProjectConfig.LICENCE_ASSESSMENT_FAIL_ON")
    except Exception as error:
        return [f"LICENCE_ASSESSMENT configuration is invalid: {error}"]
    return []


PROJECT_CONFIG_SCHEMA: Dict[str, FieldSchema] = {
    ConfigurationVariable.PROJECT_ROOT.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.PROJECT_CONFIG.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.NEWS_DIR.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.VERSION_FILE_PATH.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.CHANGELOG_FILE_PATH.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.MODULE_TO_DOCUMENT.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.DOCUMENTATION_DEFAULT_OUTPUT_PATH.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.DOCUMENTATION_PRODUCTION_OUTPUT_PATH.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.GIT_TOKEN.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.BETA_BRANCH.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.MASTER_BRANCH.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.RELEASE_BRANCH_PATTERN.name: FieldSchema(_validate_regex),
    ConfigurationVariable.REMOTE_ALIAS.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.LOGGER_FORMAT.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.BOT_USERNAME.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.BOT_EMAIL.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.ORGANISATION.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.ORGANISATION_EMAIL.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.AWS_BUCKET.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.PROJECT_NAME.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.PROJECT_UUID.name: FieldSchema(_validate_uuid),
    ConfigurationVariable.PACKAGE_NAME.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.SOURCE_DIR.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.IGNORE_REPOSITORY_TEST_UPLOAD.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.FILE_LICENCE_IDENTIFIER.name: FieldSchema(_validate_licence_expression),
    ConfigurationVariable.COPYRIGHT_START_DATE.name: FieldSchema(_validate_integer),
    ConfigurationVariable.ACCEPTED_THIRD_PARTY_LICENCES.name: FieldSchema(_validate_string_or_list_of_strings),
    ConfigurationVariable.PACKAGES_WITH_CHECKED_LICENCE.name: FieldSchema(_validate_checked_licences),
    ConfigurationVariable.PROGRAMMING_LANGUAGE.name: FieldSchema(_validate_language),
    ConfigurationVariable.AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.DEPENDENCY_UPDATE_BRANCH_PATTERN.name: FieldSchema(_validate_regex),
    ConfigurationVariable.DEPENDENCY_UPDATE_NEWS_MESSAGE.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.DEPENDENCY_UPDATE_NEWS_TYPE.name: FieldSchema(_validate_news_type),
    ConfigurationVariable.TAG_LATEST.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.TAG_VERSION_SHORTCUTS.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.SECRETS_BASELINE_FILENAME.name: FieldSchema(_validate_non_empty_string),
    ConfigurationVariable.DOCUMENTATION_GUIDES_DIR.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.DOCUMENTATION_GUIDES_OUTPUT_FOLDER.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.FAIL_ON_INCOMPLETE_LICENCE_AUDIT.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.GENERATE_LICENSING_SUMMARY_ON_RELEASE.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH.name: FieldSchema(_validate_path_string),
    ConfigurationVariable.LICENCE_ASSESSMENT_RULES.name: FieldSchema(
        lambda key, value, _dir: [] if isinstance(value, dict) else [f"{key} must be a table."]
    ),
    ConfigurationVariable.REVIEWED_LICENCE_ASSESSMENTS.name: FieldSchema(_validate_manual_reviews),
    ConfigurationVariable.LICENCE_ASSESSMENT_FAIL_ON.name: FieldSchema(_validate_string_or_list_of_strings),
    ConfigurationVariable.SKIP_DEPENDENCY_DOWNLOAD_FOR_LICENSING.name: FieldSchema(_validate_boolean),
    ConfigurationVariable.DOCUMENTATION_SITE_URL.name: FieldSchema(_validate_url),
    ConfigurationVariable.LICENCE_FILE_PATH.name: FieldSchema(_validate_path_string),
}
