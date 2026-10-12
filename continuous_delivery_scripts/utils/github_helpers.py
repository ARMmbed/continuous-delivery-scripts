#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""GitHub remote authentication and public Pages URL helpers."""

import re
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def _github_repository_path(remote: str) -> str | None:
    """Extract the repository path from a GitHub HTTPS or SSH remote."""
    if remote.startswith("git@github.com:"):
        location = remote[len("git@github.com:") :]
    else:
        parsed = urlsplit(remote)
        if parsed.hostname != "github.com" or parsed.scheme not in {"https", "http", "ssh"}:
            return None
        location = parsed.path.strip("/")
    parts = location.removesuffix(".git").strip("/").split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) for part in parts):
        return None
    return "/".join(parts)


def authenticated_github_url(remote: str, token: str) -> str:
    """Use GitHub's x-access-token HTTPS credential layout for a repository.

    Reference:
    https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github#githubs-token-formats
    """
    repository = _github_repository_path(remote)
    if not repository:
        raise ValueError("Not a GitHub repository remote")
    suffix = ".git" if remote.rstrip("/").endswith(".git") else ""
    return f"https://x-access-token:{token}@github.com/{repository}{suffix}"


def github_pages_candidate(remote: str) -> str | None:
    """Derive the conventional GitHub Pages address from a GitHub remote."""
    repository = _github_repository_path(remote)
    if not repository:
        return None
    owner, name = repository.split("/")
    return (
        f"https://{owner}.github.io/"
        if name.lower() == f"{owner.lower()}.github.io"
        else f"https://{owner}.github.io/{name}/"
    )


@lru_cache(maxsize=32)
def _verified_pages_url(candidate: str) -> str | None:
    """Use a Pages candidate only when the public site responds with HTML."""
    try:
        request = Request(candidate, headers={"User-Agent": "continuous-delivery-scripts"}, method="HEAD")
        with urlopen(request, timeout=3) as response:
            if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                return None
            final_url = response.geturl()
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    parts = urlsplit(final_url)
    if parts.scheme not in {"http", "https"} or parts.hostname in {None, "github.com", "localhost", "127.0.0.1", "::1"}:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/", "", ""))


def github_pages_url(remote: str) -> str | None:
    """Find a verified public Pages site, including a redirected custom domain."""
    candidate = github_pages_candidate(remote)
    return _verified_pages_url(candidate) if candidate else None
