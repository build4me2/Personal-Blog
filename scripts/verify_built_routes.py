#!/usr/bin/env python3
"""Verify that deployment output contains the established home and article routes."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "baselines" / "preservation.json"
_SPACE = re.compile(r"\s+")
# Approved project deployment, not the historical root URL in the baseline.
DEPLOYMENT_BASE_URL = "https://build4me2.github.io/Personal-Blog/"
# Existing reviewed typography is intentionally remote, not a built asset.
# Exempt only this exact URL; it cannot substitute for the local theme CSS.
PRESERVED_FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Audiowide&family=Comfortaa:wght@400;500;600;700"
    "&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@600;700"
    "&family=Press+Start+2P&family=Tinos:wght@400;700&display=swap"
)


class RouteError(RuntimeError):
    """The built deployment tree does not satisfy the route contract."""


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href is not None:
                self.links.append(href)
        if tag == "link" and "stylesheet" in (dict(attrs).get("rel") or "").lower().split():
            self.stylesheets.append(dict(attrs).get("href") or "")

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def normalized(value: str) -> str:
    return _SPACE.sub(" ", html.unescape(value)).strip()


def deployed_url(route: str) -> str:
    """Mount a preserved site-relative identity without changing its slug."""
    return DEPLOYMENT_BASE_URL + route.lstrip("/")


def site_route(href: str, page_url: str) -> str | None:
    """Resolve a browser URL only within the exact approved deployment mount.

    Never strip an arbitrary first component or accept the old root URL. Origin,
    prefix boundary, query, and fragment checks precede local file mapping.
    """
    if not href or href != href.strip():
        return None
    try:
        parsed = urlsplit(urljoin(page_url, href))
    except ValueError:
        return None
    base = urlsplit(DEPLOYMENT_BASE_URL)
    if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
        return None
    if parsed.query or parsed.fragment or not parsed.path.startswith(base.path):
        return None
    path = unquote(parsed.path[len(base.path):])
    if "\\" in path or any(part in (".", "..") for part in path.split("/")) or path.startswith("/"):
        return None
    return "/" + path


def route_file(site: Path, route: str) -> Path:
    if route == "/":
        return site / "index.html"
    if not route.startswith("/") or not route.endswith("/") or ".." in route.split("/"):
        raise RouteError(f"invalid route in preservation baseline: {route!r}")
    return site.joinpath(*route.strip("/").split("/"), "index.html")


def verify(site: Path, baseline_path: Path = BASELINE) -> int:
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        listings = baseline["homeListing"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RouteError(f"could not read route contract: {exc}") from exc
    if not isinstance(listings, list) or len(listings) != 4:
        raise RouteError("route contract must contain exactly four home-listing entries")

    findings: list[str] = []
    pages: dict[str, PageParser] = {}
    for route, title in [("/", baseline.get("hugoConfiguration", {}).get("title"))] + [
        (entry.get("route"), entry.get("title")) for entry in listings if isinstance(entry, dict)
    ]:
        if not isinstance(route, str) or not isinstance(title, str):
            findings.append("baseline route and title values must be strings")
            continue
        path = route_file(site, route)
        relative = path.relative_to(site).as_posix()
        try:
            payload = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(f"{route}: cannot read {relative}: {exc.__class__.__name__}")
            continue
        if not payload.strip():
            findings.append(f"{route}: {relative} is empty")
            continue
        parser = PageParser()
        parser.feed(payload)
        pages[route] = parser
        if normalized(title) not in normalized(" ".join(parser.text)):
            findings.append(f"{route}: established title is missing from {relative}: {title!r}")

    for route, page in pages.items():
        stylesheets = [href for href in page.stylesheets if href != PRESERVED_FONT_STYLESHEET]
        if not stylesheets:
            findings.append(f"{route}: no local stylesheet links rendered")
        for href in stylesheets:
            css_route = site_route(href, deployed_url(route))
            if css_route is None or not css_route.endswith(".css"):
                findings.append(f"{route}: stylesheet URL is outside deployment or not CSS: {href!r}")
                continue
            css_path = site / css_route.lstrip("/")
            try:
                if not css_path.resolve().is_relative_to(site.resolve()) or not css_path.read_bytes().strip():
                    findings.append(f"{route}: stylesheet is empty or outside site: {css_route}")
            except OSError as exc:
                findings.append(f"{route}: cannot read stylesheet {css_route}: {exc.__class__.__name__}")

    home = pages.get("/")
    if home is not None:
        for entry in listings:
            if not isinstance(entry, dict) or not isinstance(entry.get("route"), str):
                continue
            route = entry["route"]
            linked_routes = {site_route(href, deployed_url("/")) for href in home.links}
            if route not in linked_routes:
                findings.append(f"/: established listing link is missing: {route}")

    if findings:
        raise RouteError("built route verification failed:\n" + "\n".join(f"- {item}" for item in sorted(set(findings))))
    return len(listings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "public")
    args = parser.parse_args()
    try:
        count = verify(args.site.resolve())
    except RouteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Built route verification passed: home and {count} established article routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
