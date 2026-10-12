#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Checks GitHub URL helpers without contacting the network."""

from unittest import TestCase, mock

from continuous_delivery_scripts.utils.github_helpers import (
    _verified_pages_url,
    authenticated_github_url,
    github_pages_candidate,
    github_pages_url,
)


class TestGitHubHelpers(TestCase):
    def test_authentication_uses_github_token_layout(self):
        self.assertEqual(
            authenticated_github_url("git@github.com:example/repository.git", "test-token"),
            "https://x-access-token:test-token@github.com/example/repository.git",
        )
        with self.assertRaisesRegex(ValueError, "Not a GitHub repository"):
            authenticated_github_url("https://gitlab.com/example/repository.git", "test-token")

    def test_only_github_remotes_produce_pages_candidates(self):
        self.assertEqual(
            github_pages_candidate("https://x-access-token:secret@github.com/owner/tool.git"),
            "https://owner.github.io/tool/",
        )
        self.assertEqual(github_pages_candidate("git@github.com:owner/owner.github.io.git"), "https://owner.github.io/")
        self.assertIsNone(github_pages_candidate("https://gitlab.com/owner/tool.git"))

    @mock.patch("continuous_delivery_scripts.utils.github_helpers.urlopen")
    def test_pages_fallback_requires_a_public_html_response(self, urlopen):
        candidate = "https://owner.github.io/site-verification-test/"
        response = urlopen.return_value.__enter__.return_value
        response.status = 200
        response.headers.get.return_value = "text/html; charset=utf-8"
        response.geturl.return_value = "https://docs.example.org/site-verification-test/"
        self.assertEqual(_verified_pages_url(candidate), "https://docs.example.org/site-verification-test/")

        other_candidate = "https://owner.github.io/nonexistent-site-verification-test/"
        response.status = 404
        self.assertIsNone(_verified_pages_url(other_candidate))

    @mock.patch("continuous_delivery_scripts.utils.github_helpers._verified_pages_url", return_value=None)
    def test_github_pages_url_does_not_publish_unverified_links(self, verified):
        self.assertIsNone(github_pages_url("https://github.com/owner/missing.git"))
        verified.assert_called_once_with("https://owner.github.io/missing/")
