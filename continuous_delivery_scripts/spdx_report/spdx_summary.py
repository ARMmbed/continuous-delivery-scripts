#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Summary generators."""
import datetime
import jinja2
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from continuous_delivery_scripts.spdx_report.spdx_helpers import get_package_manual_check
from continuous_delivery_scripts.spdx_report.spdx_package import SpdxPackage

JINJA_TEMPLATE_SUMMARY_HTML = "third_party_IP_report.html.jinja2"
JINJA_TEMPLATE_SUMMARY_CSV = "third_party_IP_report.csv.jinja2"
JINJA_TEMPLATE_SUMMARY_TEXT = "third_party_IP_report.txt.jinja2"
JINJA_TEMPLATES = [JINJA_TEMPLATE_SUMMARY_HTML, JINJA_TEMPLATE_SUMMARY_CSV, JINJA_TEMPLATE_SUMMARY_TEXT]
logger = logging.getLogger(__name__)
try:
    jinja2_env = jinja2.Environment(
        loader=jinja2.PackageLoader("continuous_delivery_scripts.spdx_report.spdx_summary", "templates"),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
except ModuleNotFoundError as e:
    logger.error(e)


def generate_file_based_on_template(
    output_dir: Path, template_name: str, template_args: dict, suffix: str = None
) -> None:
    """Write file based on template and arguments."""
    logger.info("Loading template '%s'.", template_name)
    template = jinja2_env.get_template(template_name)
    filename = Path(template_name.rsplit(".", 1)[0])
    if suffix:
        filename = Path(
            "{0}_{2}{1}".format(
                *(str(filename.name), str(filename.suffix), str(suffix.replace(".", "_").replace("-", "_")))
            )
        )
    output_filename = output_dir.joinpath(filename)
    rendered = template.render(**template_args)
    logger.info("Writing to '%s'.", output_filename)
    output_filename.write_text(rendered, encoding="utf8")


class SummaryGenerator:
    """Licensing summary generator."""

    def __init__(self, project_package: SpdxPackage, dependencies_documents: List[SpdxPackage]) -> None:
        """Initialiser."""
        self.project = project_package
        self.all_packages = list(dependencies_documents)
        self.all_packages.append(self.project)
        self._template_arguments: Optional[dict] = None

    def _generate_template_arguments(self) -> Dict[str, Any]:
        arguments: Dict[str, Any] = dict()

        global_compliance, description_list = self._generate_packages_description()
        arguments["project"] = {
            "name": self.project.name,
            "compliance": global_compliance,
            "compliance_details": (
                f"Project [{self.project.name}]'s licence is compliant: {self.project.licence}."
                "All its dependencies are also compliant licence-wise."
            )
            if global_compliance
            else f"Project [{self.project.name}] or one, at least, of its dependencies has a non compliant licence",
        }
        arguments["packages"] = description_list
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
                is_compliant, is_licence_compliant, package_manually_checked, manual_check_details, p
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
            "is_compliant": is_compliant,
            "mark_as_problematic": not is_licence_compliant,
            "licence_compliance_details": "Licence is compliant."
            if is_licence_compliant
            else (
                f"Package's licence manually checked: {manual_check_details}"
                if package_manually_checked
                else "Licence is not compliant according to project's configuration."
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
