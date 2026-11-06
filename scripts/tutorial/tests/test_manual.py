"""The manual's own cross-checks: images, chapters, and secrets.

These are the gates that survive the re-scope. The route matrix and SHOTLOG.md belonged
to the scratch install; what is left is the claim that every picture in the manual is a
picture someone can still open, that every chapter exists, and that the credential used
to take the photographs never reaches the page.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

MANUAL = Path("docs/onboarding")
CHAPTERS = sorted(MANUAL.glob("[0-9][0-9]-*.md"))
IMAGES = sorted(MANUAL.glob("img/**/*.png"))
REFERENCE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

EXPECTED_CHAPTERS = [
    "01-sign-in",
    "02-owners-hub",
    "03-bring-the-catalogue-in",
    "04-read-the-ledger",
    "05-receive-a-delivery",
    "06-count-and-correct-stock",
    "07-remove-products",
    "08-work-the-till",
    "09-print-a-customer-receipt",
    "10-orders-and-receipts-ledger",
    "11-sales-reports-and-exports",
    "12-accounts-and-roles",
    "13-known-gaps-and-upkeep",
]

# The one place the manual shows the variable being set must show a placeholder, not a
# password — so an assignment whose value does not open with "<" is a leak.
SECRET_ASSIGNMENT = re.compile(r"TUTORIAL_SHOOT_PASSWORD[ \t]*=[ \t]*['\"]?(?!<)[^ \t'\"]{6,}")

# The harness must pull the password from the environment and nothing else: a non-empty
# fallback would be the same leak as writing it into a chapter.
PASSWORD_READ = re.compile(
    r"""PASSWORD\s*=\s*os\.environ\.get\(\s*["']TUTORIAL_SHOOT_PASSWORD["']\s*,\s*["']["']\s*\)"""
)


class ManualCrossChecksTests(SimpleTestCase):
    def test_every_chapter_is_written(self):
        present = [chapter.stem for chapter in CHAPTERS]
        self.assertEqual(present, EXPECTED_CHAPTERS)

    def test_every_image_reference_resolves(self):
        missing = []
        for chapter in [*CHAPTERS, MANUAL / "README.md"]:
            for target in REFERENCE.findall(chapter.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://")):
                    continue
                if not (MANUAL / target).is_file():
                    missing.append(f"{chapter.name} -> {target}")
        self.assertEqual(missing, [])

    def test_every_chapter_is_indexed(self):
        index = (MANUAL / "README.md").read_text(encoding="utf-8")
        unwritten = [chapter.name for chapter in CHAPTERS if chapter.name not in index]
        self.assertEqual(unwritten, [])

    def test_every_chapter_link_resolves(self):
        broken = []
        for document in sorted(MANUAL.rglob("*.md")):
            for target in re.findall(r"\]\(([^)]+\.md)\)", document.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://")):
                    continue
                if not (document.parent / target).is_file():
                    broken.append(f"{document.name} -> {target}")
        self.assertEqual(broken, [])

    def test_no_photograph_sits_unreferenced(self):
        referenced = set()
        for chapter in [*CHAPTERS, MANUAL / "README.md"]:
            base = chapter.parent
            for target in REFERENCE.findall(chapter.read_text(encoding="utf-8")):
                referenced.add(str((base / target).resolve()))
        orphans = [
            str(image.relative_to(MANUAL))
            for image in IMAGES
            if str(image.resolve()) not in referenced
        ]
        self.assertEqual(orphans, [])

    def test_no_credential_reaches_the_manual(self):
        offenders = []
        for document in sorted(MANUAL.rglob("*.md")):
            text = document.read_text(encoding="utf-8")
            if SECRET_ASSIGNMENT.search(text):
                offenders.append(f"{document.name} assigns a real value to the shoot password")
        self.assertEqual(offenders, [])

    def test_the_harness_holds_no_password_of_its_own(self):
        source = Path("scripts/tutorial/shoot_live.py").read_text(encoding="utf-8")
        self.assertTrue(
            PASSWORD_READ.search(source),
            "the harness must read TUTORIAL_SHOOT_PASSWORD with an empty fallback",
        )

    def test_chapter_headings_follow_the_anatomy(self):
        blocks = (
            "## What this is for",
            "## You need",
            "## Steps",
            "## When it goes wrong",
            "## Notes & limits",
        )
        broken = []
        for chapter in CHAPTERS:
            text = chapter.read_text(encoding="utf-8")
            for block in blocks:
                if block not in text:
                    broken.append(f"{chapter.name} has no {block!r}")
        self.assertEqual(broken, [])
