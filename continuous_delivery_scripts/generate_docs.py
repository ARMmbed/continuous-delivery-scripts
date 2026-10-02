#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Generates documentation."""

import argparse
from html import escape
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import markdown

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


def _html_guide_link(match: re.Match[str]) -> str:
    """Link to the rendered HTML page instead of its Markdown source."""
    return f'href="{match.group(1)}.html{match.group(2) or ""}"'


def _html_page(title: str, description: str, body: str, nav_prefix: str = "..", has_api_index: bool = True) -> str:
    """Wrap a task guide in a standalone, readable HTML page."""
    api_link = f' · <a href="{nav_prefix}/api.html">API reference</a>' if has_api_index else ""
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(title)}</title><meta name="description" content="{escape(description, quote=True)}">'
        "<style>body{font:1.1rem/1.6 system-ui,sans-serif;max-width:76ch;margin:2rem auto;padding:0 1rem}"
        "a{color:#075985}pre{overflow:auto;background:#f3f4f6;padding:1rem}code{overflow-wrap:anywhere}"
        "nav{border-bottom:1px solid #ccc;padding-bottom:1rem}li{margin:.4rem 0}</style>"
        f'</head><body><nav><a href="{nav_prefix}/index.html">Overview</a>{api_link}</nav>'
        f"<main>{body}</main></body></html>\n"
    )


def _preserve_api_navigation(output_directory: Path, guide_output: Path) -> None:
    """Keep links to the original API index working after it becomes api.html."""
    original_index = output_directory / "index.html"
    if not original_index.is_file():
        return
    original_index.rename(output_directory / "api.html")

    for page in output_directory.rglob("*.html"):
        if page.is_relative_to(guide_output):
            continue

        def retarget(match: re.Match[str]) -> str:
            destination = match.group(1)
            relative_path = destination.split("#", 1)[0]
            if (page.parent / relative_path).resolve() != original_index.resolve():
                return match.group(0)
            return f'href="{destination.replace("index.html", "api.html")}"'

        contents = page.read_text(encoding="utf8")
        updated = re.sub(r'href="((?:\.\./|\./)*index\.html(?:#[^"]*)?)"', retarget, contents)
        if updated != contents:
            page.write_text(updated, encoding="utf8")


def _guide_settings() -> tuple[Path, Path, Path, str] | None:
    """Get the optional guide source, output folder and project name."""
    configured_root = configuration.get_value_or_default(ConfigurationVariable.PROJECT_ROOT, None)
    configured_guides = configuration.get_value_or_default(ConfigurationVariable.DOCUMENTATION_GUIDES_DIR, None)
    if not configured_root or not configured_guides:
        return None
    project_root = Path(configured_root)
    project_name = str(
        configuration.get_value_or_default(ConfigurationVariable.PROJECT_NAME, project_root.name or "Project")
    )
    guide_sources = Path(configured_guides)
    if not guide_sources.is_absolute():
        guide_sources = project_root / guide_sources
    if not (guide_sources / "index.md").is_file():
        return None

    guide_folder = Path(
        str(configuration.get_value_or_default(ConfigurationVariable.DOCUMENTATION_GUIDES_OUTPUT_FOLDER, "guides"))
    )
    if guide_folder.is_absolute() or ".." in guide_folder.parts or guide_folder == Path("."):
        raise ValueError("DOCUMENTATION_GUIDES_OUTPUT_FOLDER must be a relative folder within the output directory")
    return project_root, guide_sources, guide_folder, project_name


def _render_guide(source: Path, destination: Path, project_name: str, nav_prefix: str, has_api_index: bool) -> str:
    """Render one Markdown guide to an HTML page and return its title."""
    text = source.read_text(encoding="utf8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), source.stem)
    body: str = markdown.markdown(text, extensions=["fenced_code", "tables"])
    body = re.sub(r'href="([a-z0-9-]+)\.md(#[^"]*)?"', _html_guide_link, body)
    description = f"{title} — {project_name}."
    destination.write_text(_html_page(title, description, body, nav_prefix, has_api_index), encoding="utf8")
    return title


def _render_guides(
    guide_sources: Path, guide_output: Path, guide_folder: Path, project_name: str, has_api_index: bool
) -> list[str]:
    """Render all guides and return links for the documentation landing page."""
    guide_output.mkdir(parents=True, exist_ok=True)
    navigation_prefix = "/".join(".." for _ in guide_folder.parts)
    links = []
    for source in sorted(guide_sources.glob("*.md")):
        title = _render_guide(
            source, guide_output / f"{source.stem}.html", project_name, navigation_prefix, has_api_index
        )
        if source.stem != "index":
            links.append(
                f'<li><a href="{escape(guide_folder.as_posix())}/{escape(source.stem)}.html">{escape(title)}</a></li>'
            )
    return links


def _write_guide_index(
    output_directory: Path, project_name: str, guide_folder: Path, has_api_index: bool, links: list[str]
) -> None:
    """Write the project-specific landing page for the published guides."""
    guide_prefix = guide_folder.as_posix()
    licence = configuration.get_value_or_default(ConfigurationVariable.FILE_LICENCE_IDENTIFIER, None)
    licence_details = f"<p>Project licence: {escape(str(licence))}</p>" if licence else ""
    overview = (
        f"<h1>{escape(project_name)}</h1>"
        f"<p>Task guides for {escape(project_name)}, with setup, examples and project workflows.</p>"
        + licence_details
        + f'<p><a href="{escape(guide_prefix)}/index.html">All task guides</a>'
        + (' · <a href="api.html">API reference</a>' if has_api_index else "")
        + "</p><ul>"
        + "".join(links)
        + "</ul>"
    )
    site_description = f"Task guides{' and API reference' if has_api_index else ''} for {project_name}."
    (output_directory / "index.html").write_text(
        _html_page(f"{project_name} documentation", site_description, overview, ".", has_api_index),
        encoding="utf8",
    )


def _publish_project_guides(output_directory: Path) -> None:
    """Publish configured task guides alongside generated API documentation."""
    settings = _guide_settings()
    if settings is None:
        return
    project_root, guide_sources, guide_folder, project_name = settings
    guide_output = output_directory / guide_folder
    has_api_index = (output_directory / "index.html").is_file()
    links = _render_guides(guide_sources, guide_output, guide_folder, project_name, has_api_index)
    _preserve_api_navigation(output_directory, guide_output)
    _write_guide_index(output_directory, project_name, guide_folder, has_api_index, links)
    agent_index = project_root / "llms.txt"
    if agent_index.is_file():
        shutil.copyfile(agent_index, output_directory / "llms.txt")


def _clear_previous_docs(output_directory: Path) -> None:
    """Removes the existing output directory to avoid stale docs pages."""
    if output_directory.is_dir():
        shutil.rmtree(str(output_directory))


def generate_documentation(output_directory: Path, module_to_document: str) -> None:
    """Generates the documentation."""
    _clear_previous_docs(output_directory)
    os.makedirs(str(output_directory), exist_ok=True)
    get_language_specifics().generate_code_documentation(output_directory, module_to_document)
    _publish_project_guides(output_directory)


def generate_docs(output_directory: Path, module: str) -> int:
    """Triggers building the documentation."""
    try:
        generate_documentation(output_directory, module)
    except Exception as e:
        log_exception(logger, e)
        return 1
    return 0


def main() -> None:
    """Parses command line arguments and generates docs."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output_directory",
        help="Output directory for docs html files.",
        default=configuration.get_value(ConfigurationVariable.DOCUMENTATION_DEFAULT_OUTPUT_PATH),
    )
    args = parser.parse_args()
    output_directory = Path(args.output_directory)
    module = configuration.get_value(ConfigurationVariable.MODULE_TO_DOCUMENT)
    sys.exit(generate_docs(output_directory=output_directory, module=module))


if __name__ == "__main__":
    main()
