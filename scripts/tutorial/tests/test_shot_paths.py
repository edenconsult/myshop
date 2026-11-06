"""A shot navigated to a fragment must be raw on purpose.

Markup with no `<html>` has no header and no stylesheet link, so a screenshot taken there looks like a
broken install instead of a screen. Dialogs belong in a shot's `steps`, where the harness clicks the
button that loads them; a `path` is a page. Two shots break that rule, and each one is exempt only
because a chapter has to show the rawness itself, so this gate's job is to catch the third one nobody
thought about.

`/orders/check-orders/` is linked from nowhere, so the only way anyone reaches it is by typing it, and
what they get is an unstyled block with no chrome. Chapter 10 has to say that, so the picture has to be
allowed to show it. `/orders/sell-products/` is the register's own fragment address: typed in, it is the
same register with its clothes off, which is the one way to show the true order of the controls and that
the phone's `In cart` / `Back to products` / `Pay` bar is part of every register. Chapter 08 step 7 is
that lesson, so the frame stays. Every new exemption needs a sentence here saying what the rawness proves.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from scripts.tutorial.shoot_live import plan

DELIBERATELY_RAW = {"10-today-legacy", "08-register"}


class ShotPathTests(TestCase):
    def test_every_navigated_path_renders_a_whole_document(self):
        Account = get_user_model()
        clients = {
            "anon": Client(),
            "admin": Client(),
            "cashier": Client(),
        }
        clients["admin"].force_login(
            Account.objects.create(username="gate-owner", user_type="ADMIN", is_staff=True)
        )
        clients["cashier"].force_login(
            Account.objects.create(username="gate-counter", user_type="SALEPERSON")
        )

        fragments = []
        for shot in plan():
            if shot.name in DELIBERATELY_RAW:
                continue
            response = clients[shot.role].get(shot.path, follow=True)
            if b"<html" not in response.content:
                fragments.append(
                    f"{shot.name}: {shot.path} -> {response.status_code}, {len(response.content)} bytes"
                )
        self.assertEqual(fragments, [])
