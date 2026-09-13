#!/usr/bin/env python3
"""Offline tests for deployment-output route verification."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_built_routes", ROOT / "scripts" / "verify_built_routes.py"
)
assert SPEC and SPEC.loader
routes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(routes)


class BuiltRouteTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        site = root / "public"
        entries = [
            {"route": f"/article-{index}/", "title": f"Article {index}"}
            for index in range(1, 5)
        ]
        baseline = root / "preservation.json"
        baseline.write_text(
            json.dumps({"hugoConfiguration": {"title": "Site title"}, "homeListing": entries}),
            encoding="utf-8",
        )
        site.mkdir()
        links = "".join(
            f'<a href="/Personal-Blog{entry["route"]}">{entry["title"]}</a>' for entry in entries
        )
        css = site / "assets/css/style.css"
        css.parent.mkdir(parents=True)
        css.write_text("body { color: black; }\n", encoding="utf-8")
        stylesheet = '<link rel="stylesheet" href="/Personal-Blog/assets/css/style.css">'
        (site / "index.html").write_text(
            f"<html><head>{stylesheet}</head><body>Site title{links}</body></html>", encoding="utf-8"
        )
        for entry in entries:
            output = site / entry["route"].strip("/")
            output.mkdir()
            (output / "index.html").write_text(
                f'<html><head>{stylesheet}</head><h1>{entry["title"]}</h1></html>', encoding="utf-8"
            )
        return site, baseline

    def test_accepts_home_and_exactly_four_nonempty_article_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site, baseline = self.fixture(Path(temporary))
            self.assertEqual(routes.verify(site, baseline), 4)

    def test_missing_route_fails_with_stable_actionable_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site, baseline = self.fixture(Path(temporary))
            (site / "article-3" / "index.html").unlink()
            with self.assertRaises(routes.RouteError) as raised:
                routes.verify(site, baseline)
        self.assertEqual(
            str(raised.exception),
            "built route verification failed:\n"
            "- /article-3/: cannot read article-3/index.html: FileNotFoundError",
        )

    def test_home_must_link_every_established_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site, baseline = self.fixture(Path(temporary))
            home = site / "index.html"
            home.write_text(home.read_text(encoding="utf-8").replace('href="/Personal-Blog/article-2/"', 'href="/wrong/"'), encoding="utf-8")
            with self.assertRaisesRegex(routes.RouteError, "established listing link is missing: /article-2/"):
                routes.verify(site, baseline)

    def test_listing_requires_exact_deployment_origin_and_prefix(self) -> None:
        good = [
            "/Personal-Blog/article-2/",
            "https://build4me2.github.io/Personal-Blog/article-2/",
            "article-2/",
        ]
        bad = [
            "/article-2/",
            "https://build4me2.github.io/article-2/",
            "https://wrong.example/Personal-Blog/article-2/",
            "/Personal-Blogger/article-2/",
            "/personal-blog/article-2/",
            "/Personal-Blog/Personal-Blog/article-2/",
            "/Personal-Blog/article-2/?wrong=1",
            "/Personal-Blog/article-2/#wrong",
        ]
        for href in good + bad:
            with self.subTest(href=href), tempfile.TemporaryDirectory() as temporary:
                site, baseline = self.fixture(Path(temporary))
                home = site / "index.html"
                home.write_text(home.read_text().replace(
                    'href="/Personal-Blog/article-2/"', f'href="{href}"'
                ), encoding="utf-8")
                if href in good:
                    self.assertEqual(routes.verify(site, baseline), 4)
                else:
                    with self.assertRaisesRegex(routes.RouteError, "established listing link is missing: /article-2/"):
                        routes.verify(site, baseline)

    def test_stylesheets_require_prefixed_urls_and_nonempty_local_css_on_every_page(self) -> None:
        mutations = [
            "root-url", "wrong-origin", "missing-file", "empty-file",
            "whitespace-file", "missing-link", "non-css", "encoded-traversal",
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                site, baseline = self.fixture(Path(temporary))
                article = site / "article-2/index.html"
                payload = article.read_text()
                href = "/Personal-Blog/assets/css/style.css"
                if mutation == "root-url":
                    payload = payload.replace(href, "/assets/css/style.css")
                elif mutation == "wrong-origin":
                    payload = payload.replace(href, "https://wrong.example" + href)
                elif mutation == "missing-file":
                    (site / "assets/css/style.css").unlink()
                elif mutation in ("empty-file", "whitespace-file"):
                    (site / "assets/css/style.css").write_text(
                        "" if mutation == "empty-file" else " \n\t", encoding="utf-8"
                    )
                elif mutation == "missing-link":
                    payload = payload.replace(f'<link rel="stylesheet" href="{href}">', "")
                elif mutation == "non-css":
                    payload = payload.replace(href, "/Personal-Blog/index.html")
                else:
                    payload = payload.replace(href, "/Personal-Blog/%2e%2e/assets/css/style.css")
                article.write_text(payload, encoding="utf-8")
                with self.assertRaisesRegex(routes.RouteError, "/article-2/: .*stylesheet"):
                    routes.verify(site, baseline)

    def test_preserved_external_fonts_cannot_substitute_for_local_stylesheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site, baseline = self.fixture(Path(temporary))
            home = site / "index.html"
            payload = home.read_text()
            font = f'<link rel="stylesheet" href="{routes.PRESERVED_FONT_STYLESHEET}">'
            home.write_text(payload.replace("</head>", font + "</head>"), encoding="utf-8")
            self.assertEqual(routes.verify(site, baseline), 4)
            home.write_text(payload.replace(
                "/Personal-Blog/assets/css/style.css", routes.PRESERVED_FONT_STYLESHEET
            ), encoding="utf-8")
            with self.assertRaisesRegex(routes.RouteError, "no local stylesheet links rendered"):
                routes.verify(site, baseline)

    def test_real_build_stylesheets_resolve_and_articles_retain_project_prefix(self) -> None:
        from scripts import build_site

        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            setup = subprocess.run(
                ["python3", "scripts/setup_pinned_theme.py"], cwd=ROOT,
                text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(setup.returncode, 0, setup.stderr)
            build_site.build(site)
            self.assertEqual(routes.verify(site), 4)
            baseline = json.loads(routes.BASELINE.read_text())
            entries = baseline["homeListing"]
            home = routes.PageParser()
            home.feed((site / "index.html").read_text())
            for entry in entries:
                self.assertIn(routes.deployed_url(entry["route"]), home.links)
            for route in ["/"] + [entry["route"] for entry in entries]:
                page = routes.PageParser()
                page.feed(routes.route_file(site, route).read_text())
                self.assertIn(routes.PRESERVED_FONT_STYLESHEET, page.stylesheets)
                local_stylesheets = [
                    href for href in page.stylesheets if href != routes.PRESERVED_FONT_STYLESHEET
                ]
                self.assertTrue(local_stylesheets)
                for href in local_stylesheets:
                    resolved = urljoin(routes.deployed_url(route), href)
                    self.assertTrue(resolved.startswith(routes.DEPLOYMENT_BASE_URL), href)
                    relative = resolved.removeprefix(routes.DEPLOYMENT_BASE_URL)
                    self.assertTrue(relative.endswith(".css"), href)
                    self.assertTrue((site / relative).read_bytes().strip(), href)


if __name__ == "__main__":
    unittest.main()
