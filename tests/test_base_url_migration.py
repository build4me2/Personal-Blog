#!/usr/bin/env python3
"""The approved deployment change is an exact exception, not a rebaseline."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validate_preservation_baseline as validator

ROOT = Path(__file__).resolve().parents[1]


class BaseURLMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = json.loads((ROOT / "tests/baselines/preservation.json").read_text())
        self.reviews = json.loads((ROOT / "tests/baselines/review-records.json").read_text())
        self.current = (ROOT / "hugo.toml").read_bytes()
        errors: list[str] = []
        self.historical = validator.captured_file(
            self.baseline["presentationCapturedFrom"], "hugo.toml", errors
        )
        self.assertEqual(errors, [])
        assert self.historical is not None

    def check_config(self, config: bytes, *, rebaseline: bool = False) -> tuple[list[str], list[str]]:
        baseline = copy.deepcopy(self.baseline)
        if rebaseline:
            baseline["protectedFiles"]["hugo.toml"] = validator.digest(config)
            # Attempt to authorize both a changed protected hash and all parsed settings.
            parsed = validator.tomllib.loads(config.decode())
            for dotted in baseline["hugoConfiguration"]:
                value = parsed
                for part in dotted.split("."):
                    value = value[part]
                baseline["hugoConfiguration"][dotted] = value
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ("content", "assets", "layouts"):
                shutil.copytree(ROOT / directory, root / directory)
            (root / "hugo.toml").write_bytes(config)
            source_errors: list[str] = []
            history_errors: list[str] = []
            real_run = subprocess.run

            def historical_git(command, **kwargs):
                # Read the real immutable Git objects, but compare temporary sources.
                self.assertEqual(command[0], "git")
                kwargs["cwd"] = ROOT
                return real_run(command, **kwargs)

            with mock.patch.object(validator, "ROOT", root), mock.patch.object(
                validator, "validate_theme_checkout", return_value=True
            ), mock.patch.object(validator.subprocess, "run", side_effect=historical_git):
                validator.validate_sources(baseline, source_errors)
                validator.validate_preservation_history(baseline, self.reviews, history_errors)
        return source_errors, history_errors

    def test_exact_approved_migration_passes_without_changing_captured_inventory(self) -> None:
        self.assertEqual(self.baseline["capturedFrom"], validator.CAPTURED_FROM_COMMIT)
        self.assertEqual(self.baseline["hugoConfiguration"]["baseURL"], validator.PRE_MIGRATION_BASE_URL)
        self.assertEqual(
            self.baseline["protectedFiles"]["hugo.toml"], validator.PRE_MIGRATION_CONFIG_SHA256
        )
        self.assertEqual(validator.approved_config_migration(self.historical), self.current)
        self.assertNotEqual(self.historical, self.current)
        self.assertEqual(self.check_config(self.current), ([], []))

    def test_root_rollback_and_other_base_urls_remain_rejected(self) -> None:
        for url in (
            "https://build4me2.github.io/",
            "https://build4me2.github.io/Other-Blog/",
            "https://build4me2.github.io/Personal-Blog",
            "https://wrong.example/Personal-Blog/",
            "http://build4me2.github.io/Personal-Blog/",
        ):
            with self.subTest(url=url):
                config = self.current.replace(
                    validator.built_routes.DEPLOYMENT_BASE_URL.encode(), url.encode()
                )
                source, history = self.check_config(config)
                self.assertTrue(any("Hugo setting baseURL" in error for error in source), source)
                self.assertIn("Hugo configuration differs from captured history", history)

    def test_unrelated_config_bytes_and_settings_remain_protected(self) -> None:
        mutations = [
            (b"title = 'Manisha Chand'", b"title = 'Changed'"),
            (b'defaultTheme = "dark"', b'defaultTheme = "light"'),
            (b'posts = "/:slug/"', b'posts = "/posts/:slug/"'),
            (b"ShowReadingTime = true", b"ShowReadingTime = false"),
            (b"unsafe = true", b"unsafe = false"),
            # These are not in the dotted-settings inventory; exact bytes still protect them.
            (b"https://github.com/build4me2", b"https://github.com/other"),
            (b'# --- Params ---', b'# changed comment'),
            (b"locale = 'en-US'", b"relativeURLs = true\nlocale = 'en-US'"),
        ]
        for before, after in mutations:
            with self.subTest(setting=before):
                self.assertIn(before, self.current)
                config = self.current.replace(before, after)
                source, history = self.check_config(config)
                self.assertIn("protected presentation/configuration changed: hugo.toml", source)
                self.assertIn("Hugo configuration differs from captured history", history)
                _, rewritten_history = self.check_config(config, rebaseline=True)
                self.assertIn("Hugo configuration differs from captured history", rewritten_history)

    def test_exception_cannot_migrate_another_config_with_the_same_base_url(self) -> None:
        other = self.historical + b"# not the approved source bytes\n"
        self.assertEqual(validator.approved_config_migration(other), other)
        migrated_other = other.replace(
            validator.PRE_MIGRATION_BASE_LINE, validator.DEPLOYMENT_BASE_LINE
        )
        self.assertEqual(
            validator.preserved_config_digest(migrated_other), validator.digest(migrated_other)
        )


if __name__ == "__main__":
    unittest.main()
