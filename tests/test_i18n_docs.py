"""Documentation translations are present and up to date (design § 8)."""

from __future__ import annotations

import sys
import unittest

from helpers import REPO

sys.path.insert(0, str(REPO / "tools"))
import i18n_check  # noqa: E402


class Translations(unittest.TestCase):
    def test_translations_are_current(self):
        problems = i18n_check.check(REPO)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_pairs_cover_readme_and_docs(self):
        targets = {t.relative_to(REPO).as_posix() for _, t in i18n_check.pairs(REPO)}
        self.assertIn("README.ko.md", targets)
        self.assertIn("docs/ko/design.md", targets)


if __name__ == "__main__":
    unittest.main()
