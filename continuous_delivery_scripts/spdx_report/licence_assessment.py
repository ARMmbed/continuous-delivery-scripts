#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Explainable, directional licence-risk screening for third-party reports.

Rules are data, not legal conclusions. The embedded TOML file can be reviewed
and selectively overridden by a project without changing this evaluator.
"""

import re
from dataclasses import dataclass, replace
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import toml
from license_expression import AND, OR, LicenseSymbol, LicenseWithExceptionSymbol, get_spdx_licensing

from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, configuration
from continuous_delivery_scripts.utils.third_party_licences import normalise_proprietary_licence
from continuous_delivery_scripts.spdx_report.scancode_licence_db import ScanCodeLicenceDB, ScanCodeLicenceInfo


class LicenceAssessment(Enum):
    """Outcomes of an advisory assessment, separate from allowlist compliance."""

    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    MANUALLY_REVIEWED = "MANUALLY_REVIEWED"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class LicenceCategory(Enum):
    """Broad screening categories, not a substitute for individual licence terms."""

    PERMISSIVE = "PERMISSIVE"
    WEAK_COPYLEFT = "WEAK_COPYLEFT"
    STRONG_COPYLEFT = "STRONG_COPYLEFT"
    NETWORK_COPYLEFT = "NETWORK_COPYLEFT"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    PROPRIETARY = "PROPRIETARY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class LicenceAssessmentResult:
    """A reportable, auditable assessment of one dependency."""

    status: LicenceAssessment
    project_licence: str
    dependency_licence: str
    reason: str
    rule: str
    source: str
    selected_licence: Optional[str] = None
    automatic_status: Optional[LicenceAssessment] = None
    manual_review_reason: str = ""
    scancode_licences: Tuple[ScanCodeLicenceInfo, ...] = ()

    def as_report(self) -> Dict[str, Any]:
        """Return JSON- and template-friendly values."""
        return {
            "status": self.status.value,
            "project_licence": self.project_licence,
            "dependency_licence": self.dependency_licence,
            "reason": self.reason,
            "rule": self.rule,
            "source": self.source,
            "selected_licence": self.selected_licence or "",
            "automatic_status": (self.automatic_status or self.status).value,
            "manual_review": {
                "reviewed": self.status is LicenceAssessment.MANUALLY_REVIEWED,
                "reason": self.manual_review_reason,
            },
            "scancode_licences": [
                {"identifier": info.identifier, "category": info.category, "url": info.url}
                for info in self.scancode_licences
            ],
        }


@dataclass(frozen=True)
class _Rule:
    """One directional, human-reviewable policy rule."""

    id: str
    status: LicenceAssessment
    reason: str
    source: str
    project_category: Optional[str] = None
    dependency_category: Optional[str] = None
    project_licence: Optional[str] = None
    dependency_licence: Optional[str] = None

    def matches(self, project: str, dependency: str, project_category: Optional[str], dependency_category: str) -> bool:
        """Match project and dependency in this order; the reverse is a different rule."""
        return bool(
            (self.project_licence is None or self.project_licence == project)
            and (self.dependency_licence is None or self.dependency_licence == dependency)
            and (
                self.project_category is None
                or (project_category is not None and self.project_category in ("*", project_category))
            )
            and (self.dependency_category is None or self.dependency_category in ("*", dependency_category))
        )

    @property
    def specificity(self) -> Tuple[int, int]:
        """Exact licence pairs take precedence over category-based screening."""
        return (
            int(self.project_licence is not None) + int(self.dependency_licence is not None),
            int(self.project_category not in (None, "*")) + int(self.dependency_category not in (None, "*")),
        )


@dataclass(frozen=True)
class _PackageOverride:
    """Explicit package decision scoped to a name and optional exact version."""

    id: str
    name: str
    version: Optional[str]
    status: LicenceAssessment
    reason: str


@dataclass(frozen=True)
class _ManualReview:
    """A recorded review of a dependency, optionally scoped to licence and version."""

    reason: str
    licence: Optional[str] = None
    version: Optional[str] = None

    def matches(self, licence: str, version: str) -> bool:
        """Only apply scoped reviews to the original reviewed terms."""
        return bool(
            (self.licence is None or self.licence == _normalise_exact(licence, "Reviewed dependency licence"))
            and (self.version is None or self.version == version)
        )


def _load_manual_reviews() -> Dict[str, _ManualReview]:
    """Read manual assessment reviews from the existing project configuration."""
    entries = configuration.get_value_or_default(ConfigurationVariable.REVIEWED_LICENCE_ASSESSMENTS, {})
    if not isinstance(entries, dict):
        raise ValueError("REVIEWED_LICENCE_ASSESSMENTS must be a table of package names and review reasons")
    reviews = {}
    for name, value in entries.items():
        package_name = _require_text(name, "Reviewed package name")
        if isinstance(value, str):
            reviews[package_name] = _ManualReview(_require_text(value, f"Review reason for {package_name}"))
        elif isinstance(value, dict):
            if set(value) - {"reason", "licence", "version"}:
                raise ValueError(f"Invalid assessment review fields for {package_name}")
            licence = value.get("licence")
            version = value.get("version")
            reviews[package_name] = _ManualReview(
                _require_text(value.get("reason"), f"Review reason for {package_name}"),
                _normalise_exact(licence, package_name),
                _require_text(version, f"Review version for {package_name}") if version is not None else None,
            )
        else:
            raise ValueError(f"Assessment review for {package_name} must contain a reason or a review table")
    return reviews


def _require_status(value: Any, context: str) -> LicenceAssessment:
    try:
        status = LicenceAssessment(value)
    except ValueError as error:
        raise ValueError(f"{context}: invalid assessment status {value!r}") from error
    if status is LicenceAssessment.MANUALLY_REVIEWED:
        raise ValueError(f"{context}: MANUALLY_REVIEWED requires a recorded manual assessment review")
    return status


def _require_category(value: Any, context: str) -> LicenceCategory:
    try:
        return LicenceCategory(value)
    except ValueError as error:
        raise ValueError(f"{context}: invalid licence category {value!r}") from error


def _require_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value.strip()


def _parse_rule(entry: dict, source: str) -> _Rule:
    allowed = {
        "id",
        "status",
        "reason",
        "project_category",
        "dependency_category",
        "project_licence",
        "dependency_licence",
    }
    if not isinstance(entry, dict) or set(entry) - allowed:
        raise ValueError(f"{source}: invalid licence assessment rule fields")
    rule_id = _require_text(entry.get("id"), "Rule ID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", rule_id):
        raise ValueError(f"Rule ID {rule_id!r} must contain only letters, numbers, dots, hyphens or underscores")
    project_category = entry.get("project_category")
    dependency_category = entry.get("dependency_category")
    if project_category is not None:
        _require_text(project_category, f"Project category for {rule_id}")
        if project_category != "*":
            _require_category(project_category, rule_id)
    if dependency_category is not None:
        _require_text(dependency_category, f"Dependency category for {rule_id}")
        if dependency_category != "*":
            _require_category(dependency_category, rule_id)
    if (project_category is None) == (entry.get("project_licence") is None):
        raise ValueError(f"{rule_id}: specify exactly one project licence or category selector")
    if (dependency_category is None) == (entry.get("dependency_licence") is None):
        raise ValueError(f"{rule_id}: specify exactly one dependency licence or category selector")
    return _Rule(
        id=rule_id,
        status=_require_status(entry.get("status"), rule_id),
        reason=_require_text(entry.get("reason"), f"Reason for {rule_id}"),
        source=source,
        project_category=project_category,
        dependency_category=dependency_category,
        project_licence=_normalise_exact(entry.get("project_licence"), rule_id),
        dependency_licence=_normalise_exact(entry.get("dependency_licence"), rule_id),
    )


def _normalise_exact(value: Any, context: str) -> Optional[str]:
    if value is None:
        return None
    expression = _require_text(value, context)
    try:
        return str(get_spdx_licensing().parse(normalise_proprietary_licence(expression)))
    except Exception as error:
        raise ValueError(f"{context}: invalid SPDX expression {expression!r}") from error


def _parse_packages(entries: Any, source: str) -> Dict[str, _PackageOverride]:
    packages: Dict[str, _PackageOverride] = {}
    if not isinstance(entries, list):
        raise ValueError(f"{source}: packages must be an array of tables")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {"id", "name", "version", "status", "reason"}:
            raise ValueError(f"{source}: invalid package override fields")
        package_id = _require_text(entry.get("id"), "Package override ID")
        if package_id in packages:
            raise ValueError(f"{source}: duplicate package override ID {package_id!r}")
        version = entry.get("version")
        packages[package_id] = _PackageOverride(
            package_id,
            _require_text(entry.get("name"), f"Package name for {package_id}"),
            _require_text(version, f"Package version for {package_id}") if version is not None else None,
            _require_status(entry.get("status"), package_id),
            _require_text(entry.get("reason"), f"Reason for {package_id}"),
        )
    return packages


class LicenceAssessmentPolicy:
    """Packaged screening rules with optional file and inline project overlays."""

    def __init__(self, default: dict, override: Optional[dict] = None, inline_override: Optional[dict] = None) -> None:
        """Validate and merge classifications, rules and package exceptions."""
        self.classifications: Dict[str, LicenceCategory] = {}
        self.scancode_categories: Dict[str, LicenceCategory] = {}
        self.rules: Dict[str, _Rule] = {}
        self.packages: Dict[str, _PackageOverride] = {}
        self.fail_on: Tuple[LicenceAssessment, ...] = ()
        for data, source in ((default, "built-in"), (override, "project"), (inline_override, "pyproject.toml")):
            if data is None:
                continue
            self._apply(data, source)

    @classmethod
    def from_config(cls) -> "LicenceAssessmentPolicy":
        """Load packaged defaults, an optional project file, then inline rules."""
        resource = resources.files("continuous_delivery_scripts.spdx_report").joinpath(
            "data", "licence_assessment.toml"
        )
        default = toml.loads(resource.read_text(encoding="utf8"))
        override_path = configuration.get_value_or_default(ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH, None)
        override = toml.load(Path(override_path)) if override_path else None
        inline_override = configuration.get_value_or_default(ConfigurationVariable.LICENCE_ASSESSMENT_RULES, None)
        return cls(default, override, inline_override)

    def _apply(self, data: dict, source: str) -> None:
        if not isinstance(data, dict) or set(data) - {
            "schema_version",
            "settings",
            "classifications",
            "scancode_categories",
            "rules",
            "packages",
        }:
            raise ValueError(f"{source}: unexpected licence assessment policy fields")
        if data.get("schema_version") != 1:
            raise ValueError(f"{source}: licence assessment policy requires schema_version = 1")
        settings = data.get("settings", {})
        if not isinstance(settings, dict) or set(settings) - {"fail_on"}:
            raise ValueError(f"{source}: unknown licence assessment settings")
        if "fail_on" in settings:
            values = settings["fail_on"]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValueError(f"{source}: fail_on must be a list of assessment statuses")
            self.fail_on = tuple(_require_status(value, f"{source} fail_on") for value in values)
            if LicenceAssessment.ALLOW in self.fail_on:
                raise ValueError(f"{source}: ALLOW cannot be a failing assessment status")
        classifications = data.get("classifications", {})
        if not isinstance(classifications, dict):
            raise ValueError(f"{source}: classifications must be a table")
        for identifier, category in classifications.items():
            self.classifications[_require_text(identifier, "Licence identifier")] = _require_category(
                category, identifier
            )
        categories = data.get("scancode_categories", {})
        if not isinstance(categories, dict):
            raise ValueError(f"{source}: scancode_categories must be a table")
        for category_name, classification in categories.items():
            self.scancode_categories[_require_text(category_name, "ScanCode category")] = _require_category(
                classification, category_name
            )
        entries = data.get("rules", [])
        if not isinstance(entries, list):
            raise ValueError(f"{source}: rules must be an array of tables")
        parsed_rules = [_parse_rule(entry, source) for entry in entries]
        if len({rule.id for rule in parsed_rules}) != len(parsed_rules):
            raise ValueError(f"{source}: duplicate licence assessment rule IDs")
        self.rules.update((rule.id, rule) for rule in parsed_rules)
        self.packages.update(_parse_packages(data.get("packages", []), source))


class LicenceAssessor:
    """Screen an SPDX dependency expression against a project licence."""

    def __init__(self, policy: LicenceAssessmentPolicy, lookup_scancode: bool = False) -> None:
        """Use the same policy for reports and optional CI gating."""
        self.policy = policy
        self._licensing = get_spdx_licensing()
        self.manual_reviews = _load_manual_reviews()
        self._scancode = ScanCodeLicenceDB() if lookup_scancode else None
        self._scancode_references: Dict[str, ScanCodeLicenceInfo] = {}

    def _lookup_info(self, identifier: str) -> Optional[ScanCodeLicenceInfo]:
        """Consult the exact SPDX key only when lookup is explicitly enabled."""
        if self._scancode is None:
            return None
        info = self._scancode.find(identifier)
        if info:
            self._scancode_references[identifier] = info
        return info

    def _category_for(self, identifier: str) -> Optional[LicenceCategory]:
        """Prefer reviewed project and embedded classifications over LicenseDB."""
        category = self.policy.classifications.get(identifier)
        if category is not None:
            return category
        info = self._lookup_info(identifier)
        return self.policy.scancode_categories.get(info.category) if info else None

    def _attach_lookup_references(
        self, result: LicenceAssessmentResult, project: str, dependency: str
    ) -> LicenceAssessmentResult:
        """Preserve where externally obtained licence information came from."""
        if not self._scancode_references:
            return result
        identifiers = set()
        for expression in (project, dependency):
            try:
                parsed = self._licensing.parse(normalise_proprietary_licence(expression))
                for symbol in parsed.symbols:
                    if isinstance(symbol, LicenseWithExceptionSymbol):
                        identifiers.add(symbol.license_symbol.key)
                    elif isinstance(symbol, LicenseSymbol):
                        identifiers.add(symbol.key)
            except (ValueError, AttributeError):
                continue
        references = tuple(
            self._scancode_references[key] for key in sorted(identifiers & self._scancode_references.keys())
        )
        if not references:
            return result
        categories = ", ".join(f"{info.identifier}: {info.category}" for info in references)
        return replace(
            result,
            reason=(
                f"{result.reason} ScanCode LicenseDB describes {categories}; "
                "its category is not a compatibility verdict."
            ),
            source=f"{result.source} + ScanCode LicenseDB",
            scancode_licences=references,
        )

    def _result(
        self,
        status: LicenceAssessment,
        project: str,
        dependency: str,
        reason: str,
        rule: str,
        source: str = "built-in",
        selected: Optional[str] = None,
    ) -> LicenceAssessmentResult:
        return LicenceAssessmentResult(status, project, dependency, reason, rule, source, selected)

    def assess(
        self,
        project_licence: str,
        dependency_licence: str,
        dependency_name: str = "",
        dependency_version: str = "",
        project_unknown: bool = False,
        dependency_unknown: bool = False,
    ) -> LicenceAssessmentResult:
        """Keep the automatic finding while recording a matching manual review."""
        automatic = self._assess_automatic(
            project_licence,
            dependency_licence,
            dependency_name,
            dependency_version,
            project_unknown,
            dependency_unknown,
        )
        automatic = self._attach_lookup_references(automatic, project_licence, dependency_licence)
        review = self.manual_reviews.get(dependency_name)
        if (
            automatic.status is LicenceAssessment.REVIEW
            and review
            and review.matches(dependency_licence, dependency_version)
        ):
            return replace(
                automatic,
                status=LicenceAssessment.MANUALLY_REVIEWED,
                automatic_status=LicenceAssessment.REVIEW,
                manual_review_reason=review.reason,
            )
        return automatic

    def _assess_automatic(
        self,
        project_licence: str,
        dependency_licence: str,
        dependency_name: str,
        dependency_version: str,
        project_unknown: bool,
        dependency_unknown: bool,
    ) -> LicenceAssessmentResult:
        """Return a conservative, directional result without invoking licence discovery."""
        project = project_licence or "Unknown"
        dependency = dependency_licence or "Unknown"
        if project_unknown or project.casefold() in ("unknown", "none", "noassertion"):
            return self._result(
                LicenceAssessment.UNKNOWN,
                project,
                dependency,
                "Project licence is not reliably known.",
                "project-unknown",
            )
        matching = [
            item
            for item in self.policy.packages.values()
            if item.name.casefold() == dependency_name.casefold()
            and (item.version is None or item.version == dependency_version)
        ]
        if matching:
            most_specific = sorted(matching, key=lambda item: item.version is not None, reverse=True)
            if len(most_specific) > 1 and most_specific[0].version == most_specific[1].version:
                raise ValueError(f"Conflicting licence assessment overrides for {dependency_name}")
            override = most_specific[0]
            return self._result(override.status, project, dependency, override.reason, override.id, "project")
        if dependency_unknown or dependency.casefold() in ("unknown", "none", "noassertion"):
            return self._result(
                LicenceAssessment.UNKNOWN,
                project,
                dependency,
                "Dependency licence is not reliably known.",
                "dependency-unknown",
            )
        try:
            project_node = self._licensing.parse(normalise_proprietary_licence(project))
            dependency_node = self._licensing.parse(normalise_proprietary_licence(dependency))
            if project_node is None or dependency_node is None:
                raise ValueError("Empty SPDX expression")
        except Exception:
            return self._result(
                LicenceAssessment.UNKNOWN,
                project,
                dependency,
                "Licence expression cannot be parsed.",
                "expression-invalid",
            )
        project_name = str(project_node)
        project_category = self._category_for(project_node.key) if isinstance(project_node, LicenseSymbol) else None
        if project_category is LicenceCategory.UNKNOWN:
            return self._result(
                LicenceAssessment.UNKNOWN,
                project,
                dependency,
                "The project licence is classified as unknown.",
                "project-unknown",
            )
        return self._assess_node(project, dependency, project_name, project_category, dependency_node)

    def _matching_rule(
        self,
        project: str,
        dependency: str,
        project_category: Optional[LicenceCategory],
        dependency_category: Optional[LicenceCategory],
    ) -> Optional[_Rule]:
        matching = [
            rule
            for rule in self.policy.rules.values()
            if rule.matches(
                project,
                dependency,
                project_category.value if project_category else None,
                dependency_category.value if dependency_category else "UNKNOWN",
            )
        ]
        if not matching:
            return None
        matching.sort(key=lambda rule: rule.specificity, reverse=True)
        if len(matching) > 1 and matching[0].specificity == matching[1].specificity:
            raise ValueError(f"Conflicting licence assessment rules: {matching[0].id} and {matching[1].id}")
        return matching[0]

    def _assess_node(
        self, project: str, dependency: str, project_name: str, project_category: Optional[LicenceCategory], node: Any
    ) -> LicenceAssessmentResult:
        name = str(node)
        category = self._category_for(node.key) if isinstance(node, LicenseSymbol) else None
        rule = self._matching_rule(project_name, name, project_category, category)
        if rule:
            return self._result(rule.status, project, dependency, rule.reason, rule.id, rule.source, name)
        if isinstance(node, LicenseSymbol) and category is not None:
            self._lookup_info(node.key)
        if category is LicenceCategory.UNKNOWN:
            return self._result(
                LicenceAssessment.UNKNOWN,
                project,
                dependency,
                f"The dependency licence {name} is classified as unknown.",
                "dependency-unknown",
                selected=name,
            )
        if not project_category:
            return self._result(
                LicenceAssessment.REVIEW,
                project,
                dependency,
                "Project licence is unclassified or offers multiple terms; "
                "determine the applicable terms before comparison.",
                "project-needs-review",
            )
        if isinstance(node, OR):
            branches = [
                self._assess_node(project, dependency, project_name, project_category, part) for part in node.args
            ]
            for status in (
                LicenceAssessment.ALLOW,
                LicenceAssessment.REVIEW,
                LicenceAssessment.UNKNOWN,
                LicenceAssessment.DENY,
            ):
                selected = next((branch for branch in branches if branch.status is status), None)
                if selected:
                    return self._result(
                        status,
                        project,
                        dependency,
                        f"An OR choice of {selected.selected_licence or name} is {status.value}: {selected.reason}",
                        "expression-or",
                        source=selected.source,
                        selected=selected.selected_licence,
                    )
        if isinstance(node, AND):
            branches = [
                self._assess_node(project, dependency, project_name, project_category, part) for part in node.args
            ]
            for status in (
                LicenceAssessment.DENY,
                LicenceAssessment.UNKNOWN,
                LicenceAssessment.REVIEW,
                LicenceAssessment.ALLOW,
            ):
                if any(branch.status is status for branch in branches):
                    source = "project" if any(branch.source == "project" for branch in branches) else "built-in"
                    return self._result(
                        status,
                        project,
                        dependency,
                        "All AND obligations apply: "
                        + "; ".join(f"{branch.selected_licence}: {branch.reason}" for branch in branches),
                        "expression-and",
                        source=source,
                        selected=name,
                    )
        if isinstance(node, LicenseWithExceptionSymbol):
            self._lookup_info(node.license_symbol.key)
            return self._result(
                LicenceAssessment.REVIEW,
                project,
                dependency,
                f"The exception in {name} has not been reviewed in the configured policy.",
                "exception-needs-review",
                selected=name,
            )
        if isinstance(node, LicenseSymbol):
            if name.startswith("LicenseRef-"):
                reason = f"The terms of the project-defined licence reference {name} need human review."
                status = LicenceAssessment.REVIEW
                identifier = "licence-reference-needs-review"
            elif category is not None:
                reason = f"No directional assessment rule is defined for {name}; review its obligations."
                status = LicenceAssessment.REVIEW
                identifier = "directional-rule-missing"
            else:
                reason = f"No classification or directional rule is available for {name}."
                status = LicenceAssessment.UNKNOWN
                identifier = "licence-unclassified"
            return self._result(status, project, dependency, reason, identifier, selected=name)
        return self._result(
            LicenceAssessment.UNKNOWN, project, dependency, "Unsupported SPDX expression.", "expression-unsupported"
        )
