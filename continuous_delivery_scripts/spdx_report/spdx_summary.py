#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Summary generators."""

import datetime
import json
import jinja2
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from continuous_delivery_scripts.spdx_report.spdx_helpers import (
    get_package_manual_check,
)
from continuous_delivery_scripts.spdx_report.spdx_package import SpdxPackage
from continuous_delivery_scripts.utils.third_party_licences import UNKNOWN_LICENCE

JINJA_TEMPLATE_SUMMARY_HTML = "third_party_IP_report.html.jinja2"
JINJA_TEMPLATE_SUMMARY_CSV = "third_party_IP_report.csv.jinja2"
JINJA_TEMPLATE_SUMMARY_TEXT = "third_party_IP_report.txt.jinja2"
JINJA_TEMPLATES = [
    JINJA_TEMPLATE_SUMMARY_HTML,
    JINJA_TEMPLATE_SUMMARY_CSV,
    JINJA_TEMPLATE_SUMMARY_TEXT,
]
logger = logging.getLogger(__name__)


def _link_report_from_index(output_dir: Path) -> None:
    """Link the completed TPIP report from a generated documentation index, when present."""
    index = output_dir / "index.html"
    report = output_dir / JINJA_TEMPLATE_SUMMARY_HTML.removesuffix(".jinja2")
    if not index.is_file() or not report.is_file():
        return
    contents = index.read_text(encoding="utf8")
    report_href = f'href="{report.name}"'
    if report_href in contents:
        return
    link = (
        '<section id="third-party-ip-report"><h2>Third-party IP and licence report</h2>'
        f"<p><a {report_href}>View the report</a></p></section>"
    )
    for closing_tag in ("</main>", "</body>"):
        if closing_tag in contents:
            index.write_text(contents.replace(closing_tag, f"{link}{closing_tag}", 1), encoding="utf8")
            return


def _get_jinja2_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(Path(__file__).resolve().parent.joinpath("templates"))),
        autoescape=lambda name: bool(name and name.endswith(".html.jinja2")),
    )


def generate_file_based_on_template(
    output_dir: Path,
    template_name: str,
    template_args: dict,
    suffix: Optional[str] = None,
) -> None:
    """Write file based on template and arguments."""
    logger.info("Loading template '%s'.", template_name)
    template = _get_jinja2_env().get_template(template_name)
    filename = Path(template_name.rsplit(".", 1)[0])
    if suffix:
        filename = Path(
            "{0}_{2}{1}".format(
                *(
                    str(filename.name),
                    str(filename.suffix),
                    str(suffix.replace(".", "_").replace("-", "_")),
                )
            )
        )
    output_filename = output_dir.joinpath(filename)
    rendered = template.render(**template_args)
    logger.info("Writing to '%s'.", output_filename)
    output_filename.write_text(rendered, encoding="utf8")


class SummaryGenerator:
    """Licensing summary generator."""

    def __init__(
        self,
        project_package: SpdxPackage,
        dependencies_documents: List[SpdxPackage],
        missing_dependencies: Optional[List[str]] = None,
    ) -> None:
        """Initialiser."""
        self.project = project_package
        self.all_packages = list(dependencies_documents)
        self.all_packages.append(self.project)
        self.missing_dependencies = sorted(set(missing_dependencies or []))
        self._template_arguments: Optional[dict] = None

    def _generate_template_arguments(self) -> Dict[str, Any]:
        arguments: Dict[str, Any] = dict()

        global_compliance, description_list = self._generate_packages_description()
        arguments["project"] = {
            "name": self.project.name,
            "compliance": global_compliance,
            "compliance_details": (
                (
                    f"Project [{self.project.name}]'s licence is compliant: {self.project.licence}."
                    "All its dependencies are also compliant licence-wise."
                )
                if global_compliance
                else f"Project [{self.project.name}] or one, at least, of its dependencies has a non compliant licence"
            ),
        }
        arguments["packages"] = description_list
        arguments["missing_dependencies"] = self.missing_dependencies
        arguments["unknown_licences"] = sorted(
            p.name
            for p in self.all_packages
            if p.metadata.has_unknown_licence or p.main_licence == UNKNOWN_LICENCE.identifier
        )
        arguments["unreviewed_licences"] = [
            name for name in arguments["unknown_licences"] if not get_package_manual_check(name)[1]
        ]
        arguments["undocumented_exemptions"] = sorted(
            p.name
            for p in self.all_packages
            if get_package_manual_check(p.name)[0] and not get_package_manual_check(p.name)[1]
        )
        arguments["project"]["complete"] = not (
            self.missing_dependencies or arguments["unreviewed_licences"] or arguments["undocumented_exemptions"]
        )
        if not arguments["project"]["complete"]:
            details = "Incomplete audit: review missing dependencies, unknown licences and undocumented exemptions."
            arguments["project"]["compliance_details"] = details
        arguments["render_time"] = datetime.datetime.now()
        return arguments

    def _generate_packages_description(self) -> Tuple[bool, dict]:
        description_list = dict()
        global_compliance = True
        for p in self.all_packages:
            main_licence_valid = p.is_main_licence_accepted
            actual_licence_valid = p.is_licence_accepted
            package_manually_checked, manual_check_details = get_package_manual_check(p.name)
            is_licence_compliant = main_licence_valid and actual_licence_valid
            is_compliant = is_licence_compliant or package_manually_checked
            if not is_compliant:
                global_compliance = False
            description_list[p.name] = self._generate_description_for_one_package(
                is_compliant,
                is_licence_compliant,
                package_manually_checked,
                manual_check_details,
                p,
            )

        return global_compliance, description_list

    def _generate_description_for_one_package(
        self,
        is_compliant: bool,
        is_licence_compliant: bool,
        package_manually_checked: bool,
        manual_check_details: Optional[str],
        p: SpdxPackage,
    ) -> dict:
        return {
            "name": p.name,
            "is_dependency": p.is_dependency,
            "url": p.url,
            "licence": p.licence,
            "version": p.version,
            "licence_source": p.metadata.licence_source,
            "declared_licence": p.metadata.declared_licence,
            "licence_classifiers": p.metadata.licence_classifiers,
            "licence_candidates": p.metadata.licence_candidates,
            "licence_evidence": p.metadata.licence_evidence,
            "manual_check": {"checked": package_manually_checked, "reason": manual_check_details or ""},
            "is_compliant": is_compliant,
            "mark_as_problematic": not is_licence_compliant,
            "licence_compliance_details": (
                "Licence is compliant."
                if is_licence_compliant
                else (
                    f"Package's licence manually checked: {manual_check_details}"
                    if package_manually_checked
                    else "Licence is not compliant according to project's configuration."
                )
            ),
        }

    @property
    def template_arguments(self) -> dict:
        """Gets template arguments."""
        if not self._template_arguments:
            self._template_arguments = self._generate_template_arguments()
        return self._template_arguments

    def generate_summary(self, dir: Path) -> None:
        """Generates a licensing summary into the specified directory.

        Args:
            dir: output directory
        """
        for t in JINJA_TEMPLATES:
            generate_file_based_on_template(dir, t, self.template_arguments)
        arguments = dict(self.template_arguments)
        arguments["render_time"] = arguments["render_time"].isoformat()
        dir.joinpath("third_party_IP_report.json").write_text(
            json.dumps(arguments, indent=2, sort_keys=True) + "\n", encoding="utf8"
        )
        _link_report_from_index(dir)
