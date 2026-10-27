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
from urllib.parse import SplitResult, urlsplit

import markdown

from continuous_delivery_scripts.language_specifics import get_language_specifics
from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.documentation_discovery import (
    documentation_site_url,
    publish_discovery_files,
    structured_data_script,
)
from continuous_delivery_scripts.utils.documentation_templates import documentation_templates
from continuous_delivery_scripts.utils.logging import log_exception

logger = logging.getLogger(__name__)


def _guide_html_path(source: Path, guide_sources: Path) -> Path:
    """Map a guide source file to its published HTML path beneath the guide output."""
    return source.relative_to(guide_sources).with_suffix(".html")


def _guide_sort_key(source: Path, guide_sources: Path) -> tuple[bool, str]:
    """Keep the top-level index first and sort the rest by relative path."""
    relative = source.relative_to(guide_sources)
    return relative != Path("index.md"), relative.as_posix()


def _rewrite_guide_link_target(parts: SplitResult, source: Path, guide_sources: Path) -> str | None:
    """Rewrite only relative Markdown links that point to published guides."""
    if parts.scheme or parts.netloc or not parts.path or parts.path.startswith("/") or not parts.path.lower().endswith(".md"):
        return None
    target = (source.parent / Path(parts.path)).resolve()
    root = guide_sources.resolve()
    if not target.is_file() or not target.is_relative_to(root):
        return None
    return parts._replace(path=f"{parts.path[:-3]}.html").geturl()


def _rewrite_rendered_guide_links(body: str, source: Path, guide_sources: Path) -> str:
    """Retarget rendered guide links to the published HTML pages."""

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        rewritten = _rewrite_guide_link_target(urlsplit(href), source, guide_sources)
        if rewritten is None:
            return match.group(0)
        return f'href="{escape(rewritten, quote=True)}"'

    return re.sub(r'href="([^"]+)"', replace, body)


def _guide_navigation_prefix(guide_folder: Path, relative_html_path: Path) -> str:
    """Build the route from a guide page back to the documentation root."""
    return "/".join(".." for _ in (guide_folder / relative_html_path.parent).parts)


def _html_page(
    title: str,
    description: str,
    body: str,
    nav_prefix: str = "..",
    has_api_index: bool = True,
    page_url: str | None = None,
    schema_type: str = "TechArticle",
) -> str:
    """Wrap a task guide in a standalone, readable HTML page."""
    return str(
        documentation_templates()
        .get_template("documentation_page.html.jinja2")
        .render(
            title=title,
            description=description,
            body=body,
            nav_prefix=nav_prefix,
            has_api_index=has_api_index,
            structured_data=structured_data_script(title, description, page_url, schema_type) if page_url else None,
        )
    )


def _update_api_navigation(output_directory: Path, guide_output: Path) -> None:
    """Preserve API index links and provide a route back to task guides."""
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
        guide_href = (
            "../" * len(page.parent.relative_to(output_directory).parts)
            + (guide_output.relative_to(output_directory) / "index.html").as_posix()
        )
        guide_link = f'<a href="{escape(guide_href, quote=True)}">Task guides</a>'
        if re.search(r"<nav\b[^>]*>", updated, flags=re.IGNORECASE):
            updated = re.sub(
                r"(<nav\b[^>]*>)",
                lambda match: f"{match.group(1)}{guide_link} · ",
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            updated = re.sub(
                r"(<body\b[^>]*>)",
                lambda match: f"{match.group(1)}<nav>{guide_link}</nav>",
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
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


def _render_guide(
    source: Path,
    destination: Path,
    guide_sources: Path,
    guide_folder: Path,
    project_name: str,
    has_api_index: bool,
    page_url: str | None,
) -> str:
    """Render one Markdown guide to an HTML page and return its title."""
    text = source.read_text(encoding="utf8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), source.stem)
    body: str = markdown.markdown(text, extensions=["fenced_code", "tables"])
    body = _rewrite_rendered_guide_links(body, source, guide_sources)
    description = f"{title} — {project_name}."
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _html_page(
            title,
            description,
            body,
            _guide_navigation_prefix(guide_folder, _guide_html_path(source, guide_sources)),
            has_api_index,
            page_url,
        ),
        encoding="utf8",
    )
    return title


def _render_guides(
    guide_sources: Path, guide_output: Path, guide_folder: Path, project_name: str, has_api_index: bool
) -> list[tuple[str, str]]:
    """Render all guides and return links for the documentation landing page."""
    guide_output.mkdir(parents=True, exist_ok=True)
    site_url = documentation_site_url()
    links = []
    for source in sorted(guide_sources.rglob("*.md"), key=lambda path: _guide_sort_key(path, guide_sources)):
        relative_html_path = _guide_html_path(source, guide_sources)
        page_url = f"{site_url}{(guide_folder / relative_html_path).as_posix()}" if site_url else None
        title = _render_guide(
            source,
            guide_output / relative_html_path,
            guide_sources,
            guide_folder,
            project_name,
            has_api_index,
            page_url,
        )
        if source.relative_to(guide_sources) != Path("index.md"):
            links.append((title, relative_html_path.as_posix()))
    return links


def _write_guide_index(
    output_directory: Path, project_name: str, guide_folder: Path, has_api_index: bool, links: list[tuple[str, str]]
) -> None:
    """Write the project-specific landing page for the published guides."""
    licence = configuration.get_value_or_default(ConfigurationVariable.FILE_LICENCE_IDENTIFIER, None)
    overview = (
        documentation_templates()
        .get_template("documentation_landing.html.jinja2")
        .render(
            project_name=project_name,
            guide_folder=guide_folder.as_posix(),
            licence=licence,
            has_api_index=has_api_index,
            links=links,
        )
    )
    site_description = f"Task guides{' and API reference' if has_api_index else ''} for {project_name}."
    (output_directory / "index.html").write_text(
        _html_page(
            f"{project_name} documentation",
            site_description,
            overview,
            ".",
            has_api_index,
            documentation_site_url(),
            "WebSite",
        ),
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
    _update_api_navigation(output_directory, guide_output)
    _write_guide_index(output_directory, project_name, guide_folder, has_api_index, links)


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
    root = configuration.get_value_or_default(ConfigurationVariable.PROJECT_ROOT, None)
    if root:
        settings = _guide_settings()
        publish_discovery_files(
            output_directory,
            Path(root),
            settings[1] if settings else None,
            settings[2] if settings else None,
            (
                settings[3]
                if settings
                else str(configuration.get_value_or_default(ConfigurationVariable.PROJECT_NAME, Path(root).name))
            ),
            module_to_document,
        )


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
