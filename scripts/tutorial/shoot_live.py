"""Photograph the shop's real screens, read-only, into docs/onboarding/img/.

Two rules shape this file. Every URL is a page the browser can land on with GET,
and every action is a click that opens a dialog or loads a partial — the write
endpoints (the /do handlers, update-stocks, toggle-active, the POST-only bulk
remove) are never touched, so running this cannot change the shop's books. The
dialog routes are htmx fragments and look broken when navigated to directly, so
each one is opened the way a person does: from the page that hosts its button.

Two shots ignore that last rule deliberately — `10-today-legacy` and `08-register`
navigate straight to a fragment address, because the unstyled picture is the point
of the chapter that holds it. `tests/test_shot_paths.py` is what keeps any third
one from slipping in by accident.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myshopproject.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

BASE_URL = os.environ.get("TUTORIAL_SHOOT_URL", "http://127.0.0.1:8000")
PASSWORD = os.environ.get("TUTORIAL_SHOOT_PASSWORD", "")
OUT = Path("docs/onboarding/img")

DESKTOP = (1440, 900)
PHONE = (390, 844)


@dataclass
class Shot:
    chapter: str
    name: str
    path: str
    role: str = "admin"  # admin | cashier | anon
    size: tuple[int, int] = DESKTOP
    steps: list[tuple] = field(default_factory=list)


def click(selector: str) -> tuple:
    return ("click", selector)


MODAL = "#modal_root > *"


def plan() -> list[Shot]:
    return [
        Shot("01-sign-in", "01-login", "/login/", "anon"),
        Shot("01-sign-in", "01-login-error", "/login/", "anon", steps=[
            ("fill", "#username", "nosuchaccount"),
            ("fill", "#password", "wrong-password"),
            ("submit",),
        ]),
        Shot("01-sign-in", "01-profile", "/profile/"),
        Shot("01-sign-in", "01-password-change", "/password/change/"),
        Shot("01-sign-in", "01-password-done", "/password/change/done/"),
        Shot("02-hub", "02-hub-admin", "/"),
        Shot("02-hub", "02-hub-phone", "/", size=PHONE),
        Shot("02-hub", "02-help", "/help/", "admin"),
        Shot("03-catalogue", "03-import-dialog", "/products/", steps=[
            click('button[hx-get*="import-products"]'),
        ]),
        Shot("03-catalogue", "03-add-product-dialog", "/products/", steps=[
            click('button[hx-get*="add-product"]'),
        ]),
        Shot("04-ledger", "04-products", "/products/"),
        Shot("04-ledger", "04-products-out-of-stock", "/products/?view=out-of-stock"),
        Shot("04-ledger", "04-edit-product-dialog", "/products/", steps=[
            click('[hx-get*="/update-product"]'),
        ]),
        Shot("05-receiving", "05-receipts", "/products/receipts/"),
        Shot("05-receiving", "05-receive-dialog", "/products/", steps=[
            click('button[hx-get*="receipts/receive"]'),
        ]),
        Shot("06-stock-count", "06-adjust-dialog", "/products/", steps=[
            click('[hx-get*="/adjust/"]'),
        ]),
        Shot("06-stock-count", "06-batches-dialog", "/products/", steps=[
            click('[hx-get*="/batches/"]'),
        ]),
        Shot("07-removal", "07-remove-one-dialog", "/products/", steps=[
            click('[hx-get*="/remove-product"]'),
        ]),
        Shot("08-till", "08-pos-admin", "/orders/?view=pos"),
        Shot("08-till", "08-pos-cashier", "/orders/?view=pos", "cashier"),
        Shot("08-till", "08-hub-cashier", "/", "cashier"),
        Shot("08-till", "08-register", "/orders/sell-products/"),
        Shot("08-till", "08-pos-phone-cashier", "/orders/?view=pos", "cashier", PHONE),
        Shot("09-printing", "09-order-inspector", "/orders/?view=orders", steps=[
            click('[hx-get*="view-order"]'),
        ]),
        Shot("10-orders", "10-orders", "/orders/?view=orders"),
        Shot("10-orders", "10-today-legacy", "/orders/check-orders/"),
        Shot("11-reports", "11-reports", "/orders/?view=reports"),
        Shot("12-accounts", "12-accounts", "/accounts/"),
        Shot("12-accounts", "12-add-salesperson", "/accounts/", steps=[
            click("text=Add salesperson"),
        ]),
    ]


def sign_in(page, username: str) -> None:
    page.goto(f"{BASE_URL}/login/", wait_until="domcontentloaded")
    page.fill("#username", username)
    page.fill("#password", PASSWORD)
    page.click("button[type=submit]", no_wait_after=True)
    page.wait_for_url(f"{BASE_URL}/", timeout=20000)


def run_steps(page, steps: list[tuple]) -> None:
    for step in steps:
        if step[0] == "fill":
            page.fill(step[1], step[2])
        elif step[0] == "submit":
            page.click("button[type=submit]", no_wait_after=True)
            page.wait_for_timeout(1500)
        elif step[0] == "click":
            page.locator(step[1]).first.click()
            page.wait_for_timeout(1200)  # the htmx swap, not a navigation


def main() -> None:
    from playwright.sync_api import sync_playwright

    if not PASSWORD:
        raise SystemExit(
            "set TUTORIAL_SHOOT_PASSWORD to the password of the tutorial accounts first; "
            "it is read from the environment so no credential lands in this file"
        )
    Account = get_user_model()
    shots = plan()
    # Re-shooting one frame after one UI change should not rewrite the other 28 files.
    only = os.environ.get("TUTORIAL_SHOOT_ONLY", "")
    if only:
        shots = [shot for shot in shots if only in shot.name]
        if not shots:
            raise SystemExit(f"no shot name contains {only!r}")
    usernames = {
        "admin": "tutorial",
        "cashier": "tutorialpos",
    }
    for role, username in usernames.items():
        if not Account.objects.filter(username=username).exists():
            raise SystemExit(f"the {role} tutorial account {username!r} is missing")

    # Every database read happens above, before the browser import: Playwright's
    # sync API owns an event loop, and Django refuses ORM calls made inside one.
    captured: list[str] = []
    skipped: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        sessions: dict[str, object] = {}
        for shot in shots:
            (OUT / shot.chapter).mkdir(parents=True, exist_ok=True)
            path = OUT / shot.chapter / f"{shot.name}.png"
            key = f"{shot.role}:{shot.size}"
            if shot.role == "anon":
                ctx = browser.new_context(viewport={"width": shot.size[0], "height": shot.size[1]})
                keep_ctx = True
            else:
                if key not in sessions:
                    ctx = browser.new_context(viewport={"width": shot.size[0], "height": shot.size[1]})
                    sign_in(ctx.new_page(), usernames[shot.role])
                    sessions[key] = ctx
                ctx = sessions[key]
                keep_ctx = False
            page = ctx.new_page()
            try:
                page.goto(f"{BASE_URL}{shot.path}", wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass  # htmx keeps a stream open; the screen is already painted
                run_steps(page, shot.steps)
                # A dialog is framed as the reader sees it: the modal over the
                # screen it dimmed, not a page stretched to its full scroll height.
                page.screenshot(path=str(path), full_page=not shot.steps)
                captured.append(f"{path}  <-  {BASE_URL}{shot.path}  [{shot.role}]")
            except Exception as exc:  # a screen that fails to open is a fact to print
                skipped.append(f"{shot.name}: {type(exc).__name__}: {str(exc).splitlines()[0]}")
            finally:
                page.close()
                if keep_ctx:
                    ctx.close()
        for ctx in sessions.values():
            ctx.close()
        browser.close()

    print("\n".join(captured))
    if skipped:
        print("\nSKIPPED:")
        print("\n".join(skipped))
    print(f"\n{len(captured)} captured, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
