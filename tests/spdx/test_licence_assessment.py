#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Directional licence screening and project policy overrides."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from continuous_delivery_scripts.spdx_report.licence_assessment import (
    LicenceAssessment,
    LicenceAssessmentPolicy,
    LicenceAssessor,
    LicenceCategory,
    verified_spdx_licence_expression,
)
from continuous_delivery_scripts.utils.configuration import ConfigurationVariable, FileConfig, configuration
from continuous_delivery_scripts.utils.third_party_licences import cleanse_licence_expression


class TestLicenceAssessment(TestCase):
    def test_packaged_policy_fails_only_deny_when_no_project_configuration_is_provided(self):
        with patch.object(configuration, "get_value_or_default", side_effect=lambda key, default: default):
            policy = LicenceAssessmentPolicy.from_config()
        self.assertEqual(policy.fail_on, (LicenceAssessment.DENY,))

    def test_this_projects_certifi_review_is_licence_scoped_across_versions(self):
        assessor = LicenceAssessor(LicenceAssessmentPolicy.from_config())
        self.assertEqual(assessor.policy.fail_on, (LicenceAssessment.DENY,))
        for version in ("2025.10.5", "2026.7.22"):
            with self.subTest(version=version):
                reviewed = assessor.assess("Apache-2.0", "MPL-2.0", "certifi", version)
                self.assertEqual(reviewed.status, LicenceAssessment.MANUALLY_REVIEWED)
        changed_licence = assessor.assess("Apache-2.0", "LGPL-2.1-only", "certifi", "2026.7.22")
        self.assertEqual(changed_licence.status, LicenceAssessment.REVIEW)
        unreviewed = assessor.assess("Apache-2.0", "MPL-2.0", "unreviewed-dependency", "1.0")
        self.assertEqual(unreviewed.status, LicenceAssessment.REVIEW)

    @classmethod
    def setUpClass(cls):
        """Exercise the packaged policy, not an in-test copy of its rules."""
        cls.assessor = LicenceAssessor(LicenceAssessmentPolicy.from_config())

    def test_default_directional_screening(self):
        cases = [
            ("BSD-3-Clause", "MIT", LicenceAssessment.ALLOW, "permissive-dependency"),
            ("BSD-3-Clause", "BSD-3-Clause", LicenceAssessment.ALLOW, "permissive-dependency"),
            ("BSD-3-Clause", "Apache-2.0", LicenceAssessment.ALLOW, "permissive-dependency"),
            ("BSD-3-Clause", "MPL-2.0", LicenceAssessment.REVIEW, "weak-copyleft-dependency"),
            ("BSD-3-Clause", "LGPL-2.1-only", LicenceAssessment.REVIEW, "weak-copyleft-dependency"),
            ("BSD-3-Clause", "GPL-2.0-only", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("BSD-3-Clause", "GPL-3.0-only", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("BSD-3-Clause", "AGPL-3.0-only", LicenceAssessment.REVIEW, "network-copyleft-dependency"),
            ("LicenseRef-Proprietary", "MIT", LicenceAssessment.ALLOW, "permissive-dependency"),
            ("LicenseRef-Proprietary", "Apache-2.0", LicenceAssessment.ALLOW, "permissive-dependency"),
            ("LicenseRef-Proprietary", "LGPL-3.0-only", LicenceAssessment.REVIEW, "weak-copyleft-dependency"),
            ("LicenseRef-Proprietary", "GPL-3.0-only", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("LicenseRef-Proprietary", "AGPL-3.0-only", LicenceAssessment.REVIEW, "network-copyleft-dependency"),
            ("GPL-2.0-only", "Apache-2.0", LicenceAssessment.REVIEW, "apache-2-to-gpl-2-only"),
            ("GPL-2.0-or-later", "Apache-2.0", LicenceAssessment.REVIEW, "apache-2-to-gpl-2-or-later"),
            ("Apache-2.0", "GPL-2.0-only", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("BSD-3-Clause", "GPL-2.0-or-later", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("GPL-2.0-only", "GPL-2.0-or-later", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("GPL-2.0-or-later", "GPL-2.0-only", LicenceAssessment.REVIEW, "strong-copyleft-dependency"),
            ("BSD-3-Clause", "CC0-1.0", LicenceAssessment.ALLOW, "public-domain-dependency"),
        ]
        for project, dependency, status, rule in cases:
            with self.subTest(project=project, dependency=dependency):
                result = self.assessor.assess(project, dependency)
                self.assertEqual((result.status, result.rule), (status, rule))
                self.assertEqual(result.project_licence, project)
                self.assertEqual(result.dependency_licence, dependency)
                self.assertTrue(result.reason)

    def test_expressions_preserve_choices_and_obligations(self):
        choice = self.assessor.assess("BSD-3-Clause", "MIT OR GPL-3.0-only")
        self.assertEqual(choice.status, LicenceAssessment.ALLOW)
        self.assertEqual(choice.selected_licence, "MIT")
        self.assertIn("MIT", choice.reason)
        combined = self.assessor.assess("BSD-3-Clause", "MIT AND GPL-3.0-only")
        self.assertEqual(combined.status, LicenceAssessment.REVIEW)
        self.assertIn("GPL-3.0-only", combined.reason)
        nested = self.assessor.assess("BSD-3-Clause", "GPL-3.0-only OR (MIT AND BSD-3-Clause)")
        self.assertEqual(nested.status, LicenceAssessment.ALLOW)
        self.assertEqual(nested.selected_licence, "MIT AND BSD-3-Clause")
        exception = "GPL-2.0-only WITH Classpath-exception-2.0"
        self.assertEqual(cleanse_licence_expression(exception), exception)
        self.assertEqual(self.assessor.assess("BSD-3-Clause", exception).rule, "exception-needs-review")

    def test_unknown_project_dependency_and_custom_references(self):
        self.assertEqual(self.assessor.assess("Unknown", "MIT").status, LicenceAssessment.UNKNOWN)
        self.assertEqual(self.assessor.assess("BSD-3-Clause", "Unknown").status, LicenceAssessment.UNKNOWN)
        self.assertEqual(
            self.assessor.assess("BSD-3-Clause", "MIT", dependency_unknown=True).status,
            LicenceAssessment.UNKNOWN,
        )
        self.assertEqual(self.assessor.assess("BSD-3-Clause", "LicenseRef-Other").status, LicenceAssessment.REVIEW)
        self.assertEqual(self.assessor.assess("LicenseRef-Other", "MIT").status, LicenceAssessment.REVIEW)
        self.assertEqual(self.assessor.assess("BSD-3-Clause", "not-a-known-licence").status, LicenceAssessment.UNKNOWN)
        unknown_policy = LicenceAssessmentPolicy(
            {"schema_version": 1, "classifications": {"MIT": "PERMISSIVE", "LicenseRef-Undetermined": "UNKNOWN"}}
        )
        self.assertEqual(
            LicenceAssessor(unknown_policy).assess("LicenseRef-Undetermined", "MIT").status,
            LicenceAssessment.UNKNOWN,
        )

    def test_unknown_dependency_uses_only_a_manually_verified_spdx_licence(self):
        verified = self.assessor.assess(
            "Apache-2.0", "Unknown", "manually-checked", dependency_unknown=True, verified_licence="BSD-3-Clause"
        )
        self.assertEqual(verified.status, LicenceAssessment.ALLOW)
        self.assertEqual(verified.dependency_licence, "BSD-3-Clause")
        self.assertEqual(verified.discovered_licence, "Unknown")
        self.assertEqual(verified.assessed_licence_source, "manual licence review")
        self.assertIn("manually verified BSD-3-Clause", verified.reason)

        for explanation in (
            "Accepted for this project since not distributed",
            "GPL-3.0-only but approved for this project",
            "BSD",
            "MIT WITH LicenseRef-UnknownException",
            "",
        ):
            with self.subTest(explanation=explanation):
                result = self.assessor.assess(
                    "Apache-2.0",
                    "Unknown",
                    "manually-checked",
                    dependency_unknown=True,
                    verified_licence=explanation,
                )
                self.assertEqual(result.status, LicenceAssessment.UNKNOWN)

        custom = self.assessor.assess(
            "Apache-2.0",
            "Unknown",
            "manually-checked",
            dependency_unknown=True,
            verified_licence="LicenseRef-Proprietary",
        )
        self.assertEqual(custom.status, LicenceAssessment.REVIEW)
        with_exception = self.assessor.assess(
            "Apache-2.0",
            "Unknown",
            "manually-checked",
            dependency_unknown=True,
            verified_licence="GPL-2.0-only WITH Classpath-exception-2.0",
        )
        self.assertEqual(with_exception.status, LicenceAssessment.REVIEW)
        self.assertEqual(with_exception.rule, "exception-needs-review")

    def test_manual_choice_extraction_is_precise_and_preserves_either_or(self):
        cases = [
            ("either Apache-2.0 or BSD-2-Clause", "Apache-2.0 OR BSD-2-Clause"),
            (
                "All contributions after December 1, 2017 released under dual license - "
                "either Apache 2.0 License or the BSD 3-Clause License.",
                "Apache-2.0 OR BSD-3-Clause",
            ),
            ("Apache-2.0 or Python-2.0", "Apache-2.0 OR Python-2.0"),
            ("MIT", "MIT"),
            ("Accepted since not distributed", None),
            ("either Apache-2.0 or unverified terms", None),
            ("not either MIT or GPL-3.0-only", None),
            ("This is an example: either MIT or GPL-3.0-only", None),
            ("either MIT or GPL-3.0-only unless sold commercially", None),
            ("either MIT or GPL-3.0-only. Further restrictions apply", None),
            ("licensed under either MIT or Apache-2.0", "Apache-2.0 OR MIT"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(verified_spdx_licence_expression(text), expected)

        overridden = self.assessor.assess(
            "Apache-2.0",
            "Apache-2.0 AND CNRI-Python",
            "regex",
            verified_licence="Apache-2.0",
        )
        self.assertEqual(overridden.status, LicenceAssessment.ALLOW)
        self.assertEqual(overridden.dependency_licence, "Apache-2.0")
        self.assertEqual(overridden.discovered_licence, "Apache-2.0 AND CNRI-Python")
        self.assertIn("could not be assessed reliably", overridden.reason)

    def test_project_policy_overrides_embedded_rules_and_classifies_custom_references(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            policy_dir = root / "policy"
            policy_dir.mkdir()
            policy_file = policy_dir / "assessment.toml"
            policy_file.write_text(
                'schema_version = 1\n[settings]\nfail_on = ["DENY"]\n'
                '[classifications]\nLicenseRef-Internal = "PROPRIETARY"\n'
                '[[rules]]\nid = "strong-copyleft-dependency"\nproject_category = "*"\n'
                'dependency_category = "STRONG_COPYLEFT"\nstatus = "DENY"\nreason = "Organisation policy."\n'
                '[[rules]]\nid = "allow-internal"\nproject_category = "PROPRIETARY"\n'
                'dependency_licence = "LicenseRef-Internal"\nstatus = "ALLOW"\nreason = "Reviewed internal licence."\n'
                '[[packages]]\nid = "approved-vendor"\nname = "vendor"\nversion = "1.2"\n'
                'status = "ALLOW"\nreason = "Reviewed agreement for version 1.2."\n',
                encoding="utf8",
            )
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[ProjectConfig]\nLICENCE_ASSESSMENT_RULES_PATH = "policy/assessment.toml"\n', encoding="utf8"
            )
            resolved = FileConfig(str(project_config)).get_value(ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH)
            self.assertEqual(Path(resolved).resolve(), policy_file.resolve())
            with patch.object(
                configuration,
                "get_value_or_default",
                side_effect=lambda key, default: (
                    resolved if key == ConfigurationVariable.LICENCE_ASSESSMENT_RULES_PATH else default
                ),
            ):
                policy = LicenceAssessmentPolicy.from_config()

        self.assertEqual(policy.classifications["LicenseRef-Internal"], LicenceCategory.PROPRIETARY)
        self.assertEqual(policy.fail_on, (LicenceAssessment.DENY,))
        assessor = LicenceAssessor(policy)
        denied = assessor.assess("BSD-3-Clause", "GPL-3.0-only")
        self.assertEqual(
            (denied.status, denied.rule, denied.source),
            (LicenceAssessment.DENY, "strong-copyleft-dependency", "project"),
        )
        self.assertEqual(assessor.assess("BSD-3-Clause", "MIT").status, LicenceAssessment.ALLOW)
        self.assertEqual(assessor.assess("BSD-3-Clause", "MIT OR GPL-3.0-only").status, LicenceAssessment.ALLOW)
        self.assertEqual(assessor.assess("BSD-3-Clause", "MIT AND GPL-3.0-only").status, LicenceAssessment.DENY)
        internal = assessor.assess("LicenseRef-Internal", "LicenseRef-Internal")
        self.assertEqual((internal.status, internal.rule), (LicenceAssessment.ALLOW, "allow-internal"))
        approved = assessor.assess("BSD-3-Clause", "GPL-3.0-only", "vendor", "1.2")
        self.assertEqual((approved.status, approved.rule), (LicenceAssessment.ALLOW, "approved-vendor"))
        self.assertEqual(assessor.assess("Unknown", "MIT", "vendor", "1.2").status, LicenceAssessment.UNKNOWN)
        self.assertEqual(
            assessor.assess("BSD-3-Clause", "GPL-3.0-only", "vendor", "1.3").status, LicenceAssessment.DENY
        )

    def test_invalid_overrides_fail_instead_of_silently_weakening_policy(self):
        default = {"schema_version": 1}
        with self.assertRaisesRegex(ValueError, "invalid licence category"):
            LicenceAssessmentPolicy(default, {"schema_version": 1, "classifications": {"MIT": "probably-safe"}})
        with self.assertRaisesRegex(ValueError, "duplicate licence assessment rule IDs"):
            LicenceAssessmentPolicy(
                default,
                {
                    "schema_version": 1,
                    "rules": [
                        {
                            "id": "same",
                            "project_category": "*",
                            "dependency_category": "PERMISSIVE",
                            "status": "ALLOW",
                            "reason": "a",
                        },
                        {
                            "id": "same",
                            "project_category": "*",
                            "dependency_category": "PERMISSIVE",
                            "status": "DENY",
                            "reason": "b",
                        },
                    ],
                },
            )
        conflicting = LicenceAssessmentPolicy(
            default,
            {
                "schema_version": 1,
                "classifications": {"MIT": "PERMISSIVE"},
                "rules": [
                    {
                        "id": "first",
                        "project_category": "PERMISSIVE",
                        "dependency_category": "PERMISSIVE",
                        "status": "ALLOW",
                        "reason": "a",
                    },
                    {
                        "id": "second",
                        "project_category": "PERMISSIVE",
                        "dependency_category": "PERMISSIVE",
                        "status": "DENY",
                        "reason": "b",
                    },
                ],
            },
        )
        with self.assertRaisesRegex(ValueError, "Conflicting licence assessment rules"):
            LicenceAssessor(conflicting).assess("MIT", "MIT")

    def test_inline_pyproject_policy_without_a_separate_file(self):
        with TemporaryDirectory() as directory:
            project_config = Path(directory) / "pyproject.toml"
            project_config.write_text(
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["DENY"]\n'
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES.classifications]\n"
                'LicenseRef-Internal = "PROPRIETARY"\n'
                "[[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]]\n"
                'id = "review-internal"\nproject_category = "PROPRIETARY"\n'
                'dependency_licence = "LicenseRef-Internal"\nstatus = "REVIEW"\n'
                'reason = "Check internal licence terms."\n'
                "[[ProjectConfig.LICENCE_ASSESSMENT_RULES.packages]]\n"
                'id = "approved-vendor"\nname = "vendor"\nversion = "1.2"\n'
                'status = "ALLOW"\nreason = "Reviewed vendor agreement."\n',
                encoding="utf8",
            )
            config = FileConfig(str(project_config))
            with patch.object(configuration, "get_value_or_default", side_effect=config.get_value_or_default):
                policy = LicenceAssessmentPolicy.from_config()

        self.assertEqual(policy.fail_on, (LicenceAssessment.DENY,))
        assessor = LicenceAssessor(policy)
        self.assertEqual(assessor.assess("BSD-3-Clause", "MIT").status, LicenceAssessment.ALLOW)
        internal = assessor.assess("LicenseRef-Internal", "LicenseRef-Internal")
        self.assertEqual(
            (internal.status, internal.rule, internal.source),
            (LicenceAssessment.REVIEW, "review-internal", "pyproject.toml"),
        )
        approved = assessor.assess("MIT", "Unknown", "vendor", "1.2", dependency_unknown=True)
        self.assertEqual((approved.status, approved.rule), (LicenceAssessment.ALLOW, "approved-vendor"))

    def test_inline_rules_take_precedence_over_file_rules(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assessment.toml").write_text(
                'schema_version = 1\n[settings]\nfail_on = ["DENY"]\n'
                '[[rules]]\nid = "strong-copyleft-dependency"\nproject_category = "*"\n'
                'dependency_category = "STRONG_COPYLEFT"\nstatus = "DENY"\nreason = "File policy."\n',
                encoding="utf8",
            )
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[ProjectConfig]\nLICENCE_ASSESSMENT_RULES_PATH = "assessment.toml"\n'
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["UNKNOWN"]\n'
                "[[ProjectConfig.LICENCE_ASSESSMENT_RULES.rules]]\n"
                'id = "strong-copyleft-dependency"\nproject_category = "*"\n'
                'dependency_category = "STRONG_COPYLEFT"\nstatus = "REVIEW"\nreason = "Inline policy."\n',
                encoding="utf8",
            )
            config = FileConfig(str(project_config))
            with patch.object(configuration, "get_value_or_default", side_effect=config.get_value_or_default):
                policy = LicenceAssessmentPolicy.from_config()

        self.assertEqual(policy.fail_on, (LicenceAssessment.UNKNOWN,))
        result = LicenceAssessor(policy).assess("BSD-3-Clause", "GPL-3.0-only")
        self.assertEqual(
            (result.status, result.source, result.reason),
            (LicenceAssessment.REVIEW, "pyproject.toml", "Inline policy."),
        )

    def test_top_level_assessment_failures_override_inline_and_file_settings(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assessment.toml").write_text(
                'schema_version = 1\n[settings]\nfail_on = ["DENY"]\n', encoding="utf8"
            )
            project_config = root / "pyproject.toml"
            project_config.write_text(
                '[ProjectConfig]\nLICENCE_ASSESSMENT_RULES_PATH = "assessment.toml"\n'
                'LICENCE_ASSESSMENT_FAIL_ON = ["UNKNOWN"]\n'
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["REVIEW"]\n',
                encoding="utf8",
            )
            config = FileConfig(str(project_config))
            with patch.object(configuration, "get_value_or_default", side_effect=config.get_value_or_default):
                self.assertEqual(LicenceAssessmentPolicy.from_config().fail_on, (LicenceAssessment.UNKNOWN,))

            project_config.write_text('[ProjectConfig]\nLICENCE_ASSESSMENT_FAIL_ON = "REVIEW"\n', encoding="utf8")
            config = FileConfig(str(project_config))
            with patch.object(configuration, "get_value_or_default", side_effect=config.get_value_or_default):
                with self.assertRaisesRegex(ValueError, "fail_on must be a list"):
                    LicenceAssessmentPolicy.from_config()

    def test_invalid_inline_policy_does_not_fall_back_to_defaults(self):
        with TemporaryDirectory() as directory:
            project_config = Path(directory) / "pyproject.toml"
            project_config.write_text(
                "[ProjectConfig.LICENCE_ASSESSMENT_RULES]\nschema_version = 1\n"
                '[ProjectConfig.LICENCE_ASSESSMENT_RULES.settings]\nfail_on = ["ALLOW"]\n',
                encoding="utf8",
            )
            config = FileConfig(str(project_config))
            with patch.object(configuration, "get_value_or_default", side_effect=config.get_value_or_default):
                with self.assertRaisesRegex(ValueError, "ALLOW cannot be a failing assessment status"):
                    LicenceAssessmentPolicy.from_config()

    def test_full_with_expression_can_be_reviewed_explicitly(self):
        exception = "GPL-2.0-only WITH Classpath-exception-2.0"
        policy = LicenceAssessmentPolicy(
            {"schema_version": 1, "classifications": {"BSD-3-Clause": "PERMISSIVE"}},
            {
                "schema_version": 1,
                "rules": [
                    {
                        "id": "reviewed-classpath-exception",
                        "project_licence": "BSD-3-Clause",
                        "dependency_licence": exception,
                        "status": "ALLOW",
                        "reason": "Human-reviewed project-specific incorporation of this exception.",
                    }
                ],
            },
        )
        result = LicenceAssessor(policy).assess("BSD-3-Clause", exception)
        self.assertEqual(
            (result.status, result.rule, result.source),
            (LicenceAssessment.ALLOW, "reviewed-classpath-exception", "project"),
        )

    def test_manual_assessment_review_is_scoped_and_keeps_the_automatic_finding(self):
        review = {
            "bar": {
                "licence": "LGPL-2.1-only",
                "version": "2.0",
                "reason": "Reviewed the distribution arrangement (LEGAL-42).",
            }
        }
        with patch.object(
            configuration,
            "get_value_or_default",
            side_effect=lambda key, default: (
                review if key == ConfigurationVariable.REVIEWED_LICENCE_ASSESSMENTS else default
            ),
        ):
            assessor = LicenceAssessor(self.assessor.policy)
        result = assessor.assess("LicenseRef-Proprietary", "LGPL-2.1-only", "bar", "2.0")
        self.assertEqual(result.status, LicenceAssessment.MANUALLY_REVIEWED)
        self.assertEqual(result.automatic_status, LicenceAssessment.REVIEW)
        self.assertEqual(result.rule, "weak-copyleft-dependency")
        self.assertIn("LEGAL-42", result.manual_review_reason)
        self.assertEqual(
            assessor.assess("LicenseRef-Proprietary", "LGPL-2.1-only", "bar", "2.1").status, LicenceAssessment.REVIEW
        )
        self.assertEqual(
            assessor.assess("LicenseRef-Proprietary", "GPL-3.0-only", "bar", "2.0").status, LicenceAssessment.REVIEW
        )
        self.assertEqual(
            assessor.assess("LicenseRef-Proprietary", "Unknown", "bar", "2.0").status, LicenceAssessment.UNKNOWN
        )

    def test_manual_review_requires_explanation_and_cannot_be_a_rule_status(self):
        with patch.object(
            configuration,
            "get_value_or_default",
            side_effect=lambda key, default: (
                {"bar": " "} if key == ConfigurationVariable.REVIEWED_LICENCE_ASSESSMENTS else default
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Review reason for bar must be a non-empty string"):
                LicenceAssessor(self.assessor.policy)
        with self.assertRaisesRegex(ValueError, "MANUALLY_REVIEWED requires a recorded manual assessment review"):
            LicenceAssessmentPolicy(
                {"schema_version": 1},
                {
                    "schema_version": 1,
                    "rules": [
                        {
                            "id": "invalid-manual-rule",
                            "project_category": "*",
                            "dependency_category": "WEAK_COPYLEFT",
                            "status": "MANUALLY_REVIEWED",
                            "reason": "Cannot be an automatic rule.",
                        }
                    ],
                },
            )
