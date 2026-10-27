#
# Copyright (C) 2020-2026 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Publish discovery files from a project's documentation and configuration."""

from html import unescape
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.documentation_templates import documentation_templates
from continuous_delivery_scripts.utils.git_helpers import get_project_remote_url
from continuous_delivery_scripts.utils.github_helpers import github_pages_url


def documentation_site_url() -> str | None:
    """Use the configured URL, or a verified public GitHub Pages site."""
    value = configuration.get_value_or_default(ConfigurationVariable.DOCUMENTATION_SITE_URL, None)
    if not value:
        root = configuration.get_value_or_default(ConfigurationVariable.PROJECT_ROOT, None)
        if not root:
            return None
        remote = get_project_remote_url(Path(root))
        return github_pages_url(remote) if remote else None
    parts = urlsplit(str(value))
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment or parts.username:
        raise ValueError("DOCUMENTATION_SITE_URL must be a public HTTP(S) base URL without query or fragment")
    if parts.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("DOCUMENTATION_SITE_URL must point to a public site")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/", "", ""))


def structured_data_script(title: str, description: str, url: str, schema_type: str) -> str:
    """Represent only known page metadata as safe JSON-LD."""
    data = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "description": description,
        "url": url,
    }
    encoded = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{encoded}</script>'


def _annotate_existing_pages(
    output: Path, site_url: str, guides: list[tuple[Path, str, str]], folder: Path | None
) -> None:
    """Annotate already-rendered landing and guide pages without rebuilding the API."""
    if not guides or folder is None:
        return
    pages = [(output / "index.html", site_url, "WebSite")]
    pages.extend(
        (output / folder / relative_html_path, f"{site_url}{folder.as_posix()}/{relative_html_path}", "TechArticle")
        for _source, _title, relative_html_path in guides
    )
    for page, url, schema_type in pages:
        text = page.read_text(encoding="utf8")
        if 'type="application/ld+json"' in text:
            continue
        title = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        description = re.search(r'<meta name="description" content="([^"]*)"', text, re.IGNORECASE)
        if title and description and "</head>" in text:
            script = structured_data_script(unescape(title.group(1)), unescape(description.group(1)), url, schema_type)
            page.write_text(text.replace("</head>", f"{script}</head>", 1), encoding="utf8")


def _guide_title(source: Path) -> str:
    return next(
        (line[2:].strip() for line in source.read_text(encoding="utf8").splitlines() if line.startswith("# ")),
        source.stem,
    )


def _guide_html_path(source: Path, sources: Path) -> Path:
    """Map a guide source file to its published HTML path beneath the guide folder."""
    return source.relative_to(sources).with_suffix(".html")


def _guide_sort_key(source: Path, sources: Path) -> tuple[bool, str]:
    """Keep the guide overview first and sort all nested guides by path."""
    relative = source.relative_to(sources)
    return relative != Path("index.md"), relative.as_posix()


def _published_guides(output: Path, sources: Path | None, folder: Path | None) -> list[tuple[Path, str, str]]:
    if sources is None or folder is None:
        return []
    guide_sources = sources
    return [
        (source, _guide_title(source), relative_html_path.as_posix())
        for source in sorted(guide_sources.rglob("*.md"), key=lambda path: _guide_sort_key(path, guide_sources))
        for relative_html_path in [_guide_html_path(source, guide_sources)]
        if (output / folder / relative_html_path).is_file()
    ]


def _render_sitemap(output: Path, site_url: str) -> str:
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", namespace)
    urlset = ElementTree.Element(f"{{{namespace}}}urlset")
    for page in sorted(output.rglob("*.html")):
        relative = page.relative_to(output).as_posix()
        url = ElementTree.SubElement(urlset, f"{{{namespace}}}url")
        ElementTree.SubElement(url, f"{{{namespace}}}loc").text = (
            site_url if relative == "index.html" else site_url + relative
        )
    ElementTree.indent(urlset, space="  ")
    return ElementTree.tostring(urlset, encoding="unicode", xml_declaration=True) + "\n"


def _render_llms_index(
    output: Path, site_url: str, name: str, guides: list[tuple[Path, str, str]], folder: Path | None
) -> str:
    """Render the concise index from pages that were actually published."""
    rendered = str(
        documentation_templates()
        .get_template("llms.txt.jinja2")
        .render(name=name, site_url=site_url, guides=guides, folder=folder, has_api=(output / "api.html").is_file())
    )
    return rendered.rstrip() + "\n"


def _render_llms_full(output: Path, site_url: str, name: str, guides: list[tuple[Path, str, str]], folder: Path) -> str:
    """Consolidate only the Markdown guides which have corresponding published pages."""
    published = {source.resolve(): relative_html_path for source, _title, relative_html_path in guides}

    sections: list[tuple[str, str]] = []
    for source, title, _relative_html_path in guides:
        text = source.read_text(encoding="utf8")
        text = re.sub(r"^# .*(?:\n|$)", "", text, count=1, flags=re.MULTILINE)

        def published_link(match: re.Match[str]) -> str:
            destination = match.group(1)
            fragment = match.group(2) or ""
            target = (source.parent / Path(destination)).resolve()
            if target not in published:
                return match.group(0)
            return f"]({site_url}{folder.as_posix()}/{published[target]}{fragment})"

        text = re.sub(r"\]\(([^)#]+\.md)(#[^)]*)?\)", published_link, text)
        in_code = False
        body = []
        for line in text.strip().splitlines():
            if line.startswith("```") or line.startswith("~~~"):
                in_code = not in_code
            if not in_code and re.match(r"^#{2,5} ", line):
                line = "#" + line
            body.append(line)
        sections.append((title, "\n".join(body)))
    api_url = f"{site_url}api.html" if (output / "api.html").is_file() else None
    rendered = str(
        documentation_templates()
        .get_template("llms-full.txt.jinja2")
        .render(name=name, sections=sections, api_url=api_url)
    )
    return rendered.rstrip() + "\n"


def _authored_directories(root: Path, guides: Path | None, module_to_document: str | None) -> list[Path]:
    """Look for overrides in the repository, guides and documented module, in that order."""
    repository = root.resolve()
    directories = [repository]

    def add(directory: Path) -> None:
        candidate = directory.resolve()
        if candidate.is_relative_to(repository) and candidate.is_dir() and candidate not in directories:
            directories.append(candidate)

    guide_directory = guides or configuration.get_value_or_default(ConfigurationVariable.DOCUMENTATION_GUIDES_DIR, None)
    if guide_directory:
        guide_path = Path(guide_directory)
        add(guide_path if guide_path.is_absolute() else repository / guide_path)

    module = module_to_document
    if module is None:
        module = configuration.get_value_or_default(ConfigurationVariable.MODULE_TO_DOCUMENT, None)
    if not module or module.strip() in {".", "./..."}:
        return directories

    source = configuration.get_value_or_default(ConfigurationVariable.SOURCE_DIR, None)
    source_path = Path(source) if source else None
    if source_path and not source_path.is_absolute():
        source_path = repository / source_path
    module_path = module.strip().removesuffix("/...").removeprefix("./")
    for relative in (module_path, module_path.replace(".", "/")):
        add(repository / relative)
        if source_path:
            add(source_path / relative)

    # SOURCE_DIR can itself be the documented module, including an import-path
    # target (for example github.com/owner/tool) whose directory is named tool.
    if source_path and source_path.name in {module_path, module_path.rsplit("/", 1)[-1]}:
        add(source_path)
    return directories


def publish_discovery_files(
    output: Path,
    root: Path,
    sources: Path | None,
    folder: Path | None,
    name: str,
    module_to_document: str | None = None,
) -> None:
    """Copy authored files by source precedence or generate applicable resources."""
    site_url = documentation_site_url()
    guides = _published_guides(output, sources, folder)
    if site_url:
        _annotate_existing_pages(output, site_url, guides, folder)
    has_pages = any(output.rglob("*.html"))
    authored_directories = _authored_directories(root, sources, module_to_document)
    for filename in ("robots.txt", "sitemap.xml", "llms.txt", "llms-full.txt"):
        destination = output / filename
        authored = next(
            (directory / filename for directory in authored_directories if (directory / filename).is_file()), None
        )
        if authored:
            if authored.resolve() != destination.resolve():
                shutil.copyfile(authored, destination)
        elif site_url and has_pages and filename == "robots.txt":
            destination.write_text(
                documentation_templates()
                .get_template("robots.txt.jinja2")
                .render(sitemap_url=f"{site_url}sitemap.xml"),
                encoding="utf8",
            )
        elif site_url and has_pages and filename == "sitemap.xml":
            destination.write_text(_render_sitemap(output, site_url), encoding="utf8")
        elif site_url and (output / "index.html").is_file() and filename == "llms.txt":
            destination.write_text(_render_llms_index(output, site_url, name, guides, folder), encoding="utf8")
        elif site_url and filename == "llms-full.txt" and guides and folder:
            destination.write_text(_render_llms_full(output, site_url, name, guides, folder), encoding="utf8")
