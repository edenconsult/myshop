# Multi-line Stock Receipts with Per-Line Selling-Price Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Book one physical delivery as one receipt of many product lines, and let a line that carries a selling price make that price the store-wide price for its product.

**Architecture:** The service already accepts a list of receipt lines and already re-prices each product's cost from them, so this feature adds one optional field to that list (`selling_price`), two nullable columns to `StockBatch` (the price a line found and the price it left behind), and a dialog that posts parallel arrays of per-line fields to one ADMIN-only view in `core/batch_views.py`. The single-product restock dialog and its view are removed, not kept alongside.

**Tech Stack:** Django 6.1, PostgreSQL, HTMX 2.0.11 (`django-htmx`), Alpine.js 3.11.1, Tailwind (class dark mode), Python 3.12 in `.venv`, Node 24 for the inline-JS compile check, WeasyPrint (untouched here).

**Spec:** `docs/superpowers/specs/2026-11-03-multi-line-receipt-pricing-design.md` — the binding authority. This plan argues from it; when the two disagree, the spec wins and the disagreement gets ruled and ledgered.

## The lane gate (read this before touching anything)

The spec's last section is a hard precondition, not a footnote. As of `7fce2a4` these paths are **uncommitted work held by a second live agent session in this same worktree**:

```
 M core/admin.py        M core/forms.py       M core/management/commands/load_csv.py
 M core/models.py       M core/tasks.py       M core/tests.py          M core/views.py
?? core/catalog_imports.py   ?? core/checkout.py      ?? core/inventory.py
?? core/management/commands/check_inventory.py
?? core/migrations/0014_…0019 (six files)    ?? core/test_catalog_imports.py  ?? core/test_inventory.py
```

**Run this gate before Step 1 of every task, for exactly the files that task touches:**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current && git status --porcelain core/models.py core/inventory.py core/views.py core/urls.py core/tests.py core/test_inventory.py core/migrations
```

- Clean output (nothing printed after the branch name) → proceed.
- Anything printed → **stop and tell the owner which file is still held.** Do not edit over another session's uncommitted work, do not stash it, and do not "commit the pile anyway". This is the failure mode the spec names: two agents editing `receive_stock` at once corrupts the ledger.
- The branch must be the branch the owner wants this feature on. Never switch branches yourself; a second session switches them under you. Re-run `git branch --show-current` immediately before every `git commit`.

Tasks 4–8 touch only `core/batch_views.py`, `core/urls.py` (route block only), and `core/templates/**` — all in this plan's own lane once Tasks 1–3 have landed. Tasks 1–3 touch the held files and are the reason this plan starts with the gate.

**Gate status as this plan was written (HEAD `7fce2a4`, 2026-11-03):** everything Tasks 1–3 need is still held — `core/models.py` is modified, `core/inventory.py` and `core/migrations/0014_…0019` are untracked. Re-run the gate before deciding:

- If those paths are now tracked and clean, run 1→9 in order.
- If they are still held, only **Task 4** and **Task 5** can be built and run green today: the picker and the dialog's GET touch nothing Tasks 1–3 create. Task 6 onward cannot — its POST builds a four-field `ReceiptLine` (Task 2), applies prices (Task 3) and asserts `StockBatch.price_applied` (Task 1). Do Tasks 4 and 5, then stop and report the block. Never start the backend edits yourself because a task is next on the list.

## Global Constraints

Every task's requirements include this section. Values are copied verbatim from the spec and the current tree.

- **English only.** All UI copy and all commit messages in English.
- **Lane gate first**, every task, on the files that task edits (above). No commit, push, merge, branch switch or migration against a shared state without the owner's yes.
- **Never interpolate a product name into a JS literal or an attribute value.** Carry catalogue values in `data-product-*` attributes and read them with `$el.dataset`. This is the only reason the picker survives products named `O'Neil "Reserve" Balm`.
- **JS-in-attribute discipline** (this repo has paid for its violation twice):
  - an attribute value in double quotes may contain **no raw `"`** — every JS string literal is single-quoted;
  - `&&` is written `&amp;&amp;`, `<` is `&lt;`, `>` is `&gt;`;
  - htmx handlers (`hx-on::*`) bind the parameter as **`event`**; Alpine handlers (`@…`, `x-on:…`) bind **`$event`** — using the wrong one throws `ReferenceError`;
  - DOM selectors inside Alpine methods are **class-based** (`.receipt-row-cost`), never `[name="…"]`, which would need a double quote.
- **Money and counts:** `GH₵ {{ value|floatformat:2|intcomma }}` for money, `|intcomma` for counts, `tnum` class on every numeric cell.
- **Icons:** local sprite only, `{% icon 'name' %}`. Names available at time of writing include `add`, `delete`, `percent`, `sell`, `inventory_2`, `receipt_long`, `insights`, `check_circle`, `dangerous`. No CDN. `scripts/build-icons.mjs` exits 1 on an unknown name.
- **After any template that introduces new Tailwind classes or a new icon name:** `npm run build` (icons + Tailwind → `static/src/output.css`) and commit the regenerated artifacts with the source change.
- **Numbers that are law:** per-line selling price `0 < price <= 9999.99` (`MAX_SELLING_PRICE`; checkout refuses any sale line above it, `core/checkout.py:157-159`); service ceilings `MAX_RECEIPT_LINES = 500` and `MAX_QUANTITY = 2_147_483_647` (`core/inventory.py:21-22`); per-line view ceiling `100_000` units (was `MAX_RESTOCK_UNITS`, `core/views.py:529`); dialog row cap `50` — a usability limit, not the correctness boundary.
- **All lines or none.** A refused receipt leaves no receipt, no batch, no shelf move and no price change. Never partial-save anything in this feature.
- **`price` is written with `bulk_update`, never with `product.save()`** — `Product.save()` raises on a stock change outside the services (`core/models.py:62-76`), and the same rule keeps the price write inside the row locks.
- **Migrations: additive only, and the human applies them.** Two nullable columns, one file, no data migration, no `RunPython`. Never run `manage.py migrate` in this plan — the dev database holds the owner's real stock and it is a shared, outward-facing system, not a scratch one. As of 2026-11-03 it is caught up through `0019`, so the file Task 1 generates is `0020` and applying it is a one-line decision for the owner: report the filename, say that no page reading `StockBatch` works until it is applied (`ProgrammingError: column core_stockbatch.price_before does not exist`), and hand over `manage.py migrate` plus the reversal `manage.py migrate core 0019`. Live verification waits for that answer; `showmigrations` (read-only) shows whether it landed.
- **Tests:** `.venv/Scripts/python.exe -B manage.py test <label> --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`. The apps are `core` and `authapp` — **there is no `sales` app.** Run one suite at a time: the test DB is shared with the second session.
- **Never create a sale or a checkout against the dev database during live verification** — it takes real sales and history is delete-protected. The live browser is the owner's ADMIN session; use a separate cookie jar for other roles and revert any probe write.
- **`core/products/response.html` is for success only.** A refused multi-line post re-renders the dialog with its lines intact (spec "Failure must not destroy the work").
- Known pre-existing failure, not yours: `core.tests.CashierReceiptTests.test_the_register_links_the_cashier_to_their_own_receipt` fails after 20:00 because `views.py:1246-1257` counts only orders inside a hard 06:00–20:00 window. Do not "fix" it in this plan; report it as the one red test with that cause.

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `core/models.py` | modify | `StockBatch.price_before` / `price_applied` — the per-line price trail |
| `core/migrations/0020_….py` | generate | one additive `AddField` × 2 (the number is the branch's next leaf) |
| `core/inventory.py` | modify | `ReceiptLine.selling_price`, its validation, its place in the fingerprint, and the price write + trail |
| `core/batch_views.py` | modify | the dialog's three endpoints (open, blank line, product search) and the parallel-array POST |
| `core/urls.py` | modify | three routes in the products include |
| `core/views.py` | modify | delete `restock_product`, `MAX_RESTOCK_UNITS`, `RESTOCK_PRESETS` (the removed single-product write) |
| `core/templates/core/products/modals/receive_stock.html` | create | the multi-line dialog |
| `core/templates/core/products/partials/receipt_line_row.html` | create | one receipt line — the only row renderer, used by GET, by failure re-render and by "Add another product" |
| `core/templates/core/products/partials/receipt_product_options.html` | create | picker options as `data-product-*` buttons |
| `core/templates/core/products/modals/restock_product.html` | delete | replaced by the two files above |
| `core/templates/core/partials/product_table_row.html` | modify | the row's Restock button points at the new dialog, prefilled |
| `core/templates/core/products/products.html` | modify | a "Receive Delivery" button for whole deliveries with no single product in mind |
| `core/templates/core/inventory/receipts.html` | modify | the priced-line marker in the Lines cell |
| `core/templates/core/inventory/receipt_detail.html` | modify | "Price was" / "Price now" columns and the below-cost flag |
| `core/batch_views.py` (`_receipt_totals`) | modify | `priced_line_count` |
| `core/test_receipt_pricing.py` | create | every test for this feature — service, view and markup |
| `core/test_batch_ui.py` | modify | `RestockDialogTests` becomes `ReceiveDialogTests` (its URL and payload shape die with the old view) |

`core/test_inventory.py`, `core/tests.py`, `core/checkout.py`, `core/forms.py` and `core/admin.py` are **not** edited. The service tests this feature needs get their own file, which is also the smallest-lane answer to a second session owning the backend's test surface.

---

### Task 1: The price trail columns on `StockBatch`

**Files:**
- Modify: `core/models.py:121-133` (`StockBatch` field block)
- Create: `core/migrations/0020_stockbatch_price_before_and_price_applied.py` (generated; 0020 is the branch's next leaf, re-check with `showmigrations core`)
- Create: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `StockBatch.price_before`, `StockBatch.price_applied` — nullable `DecimalField(max_digits=10, decimal_places=2)`. Task 3 writes them; Task 8 reads them.

- [ ] **Step 1: Run the lane gate** on `core/models.py` and `core/migrations`. If anything is dirty, stop and report which file the other session holds.

- [ ] **Step 2: Write the failing tests** — create `core/test_receipt_pricing.py` with the shared fixture every later task uses:

```python
"""Multi-line receipts and the selling prices they carry (design doc 2026-11-03).

One file for the whole feature: the service tests would otherwise sit in
core/test_inventory.py, which the backend lane holds, and the markup pins reuse
the probes core/test_batch_ui.py already paid for.
"""

import datetime as dt
import json
import re
import shutil
import subprocess
import unittest
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import migrations
from django.db.migrations.loader import MigrationLoader
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.checkout import SaleLine, checkout
from core.inventory import ReceiptLine, receive_stock
from core.models import Product, StockBatch, StockReceipt, StockReceiptSource
from core.test_batch_ui import BatchUiTestCase


def compile_js(test_case, html, **shapes):
    """Compile every rendered inline handler with the real JS engine.

    ``x-data`` is an expression, an ``@click`` handler binds ``$event`` and an
    ``hx-on::…`` handler binds ``event``. A value that compiles under one shape
    and not another is the ReferenceError class this repo has already paid for
    twice, and only node can see it.
    """
    if not shutil.which("node"):
        raise unittest.SkipTest("node is not on PATH")
    scripts = {
        "expression": "new Function('return ' + d.body)",
        "alpine": "new Function('$event', d.body)",
        "htmx": "new Function('event', d.body)",
    }
    for attribute, shape in shapes.items():
        for value in test_case.attribute_values(html, attribute):
            result = subprocess.run(
                ["node", "-e",
                 "const d=JSON.parse(require('fs').readFileSync(0,'utf8')); "
                 + scripts[shape] + ";"],
                input=json.dumps({"body": value}),
                capture_output=True,
                text=True,
            )
            test_case.assertEqual(
                result.returncode,
                0,
                f"{attribute} fails to compile as {shape}: {result.stderr.strip()}",
            )


class ReceiptPricingTestCase(BatchUiTestCase):
    """Fixture: a 18.00 priced product from the base case, plus a second product."""

    def setUp(self):
        super().setUp()
        self.bottle = Product.objects.create(
            name="Bottle Gargle", sku="BTL01", stock=3,
            cost=Decimal("4.00"), price=Decimal("7.50"),
            profit_rate=Decimal("0.47"),
        )

    def book(self, lines, *, key=None, source=StockReceiptSource.PURCHASE, reason=""):
        return receive_stock(
            actor=self.admin,
            request_key=key or uuid.uuid4(),
            lines=lines,
            received_at=timezone.now(),
            source=source,
            reason=reason,
        )


class PriceTrailColumnsTests(ReceiptPricingTestCase):
    def test_both_price_columns_are_nullable_two_place_decimals(self):
        for name in ("price_before", "price_applied"):
            field = StockBatch._meta.get_field(name)
            self.assertTrue(field.null, name)
            # blank follows the nullable columns already on this model (actor,
            # request_key); neither field is ever rendered by a ModelForm.
            self.assertTrue(field.blank, name)
            self.assertEqual(field.decimal_places, 2, name)
            self.assertEqual(field.max_digits, 10, name)

    def test_the_columns_exist_in_the_database(self):
        receipt = self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])
        batch = StockBatch.objects.get(receipt=receipt)
        StockBatch.objects.filter(pk=batch.pk).update(
            price_before=Decimal("18.00"), price_applied=Decimal("20.00")
        )
        batch.refresh_from_db()
        self.assertEqual(batch.price_before, Decimal("18.00"))
        self.assertEqual(batch.price_applied, Decimal("20.00"))

    def test_exactly_one_additive_migration_adds_both_columns(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        found = [
            (name, migration)
            for (app, name), migration in loader.disk_migrations.items()
            if app == "core"
            and any(
                isinstance(op, migrations.AddField)
                and op.model_name == "StockBatch"
                and {field.name for field in op.fields}
                & {"price_before", "price_applied"}
                for op in migration.operations
            )
        ]
        self.assertEqual(len(found), 1, f"expected one trail migration, got {[n for n, _ in found]}")
        _name, migration = found[0]
        for op in migration.operations:
            self.assertIsInstance(op, migrations.AddField, "the trail migration must be additive only")
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing -v 2 --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: three FAIL/ERRORs. `test_both_price_columns_are_nullable_two_place_decimals` raises `FieldDoesNotExist: StockBatch has no field named 'price_before'`; `test_the_columns_exist_in_the_database` raises `FieldError: Cannot resolve keyword 'price_before' into field`; `test_exactly_one_additive_migration_adds_both_columns` fails with `expected one trail migration, got []`. If any of them instead fails at import, the scaffold has pulled a symbol this task does not create — fix the import, do not add the symbol here.

- [ ] **Step 4: Add the fields** — in `core/models.py`, inside `StockBatch`, after `cost_is_estimated` (currently `:133`):

```python
    cost_is_estimated = models.BooleanField(default=False)
    # The selling price this line found and the one it left behind. Both null
    # reads as "this line changed no price", which is every pre-existing row.
    price_before = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    price_applied = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
```

- [ ] **Step 5: Generate the migration**

Run: `.venv/Scripts/python.exe -B manage.py makemigrations core --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: `core/migrations/0020_stockbatch_price_before_and_price_applied.py` (the number is whatever follows the branch's latest; the dev DB and the branch are both at `0019` as this plan was written). Open the file and confirm it contains exactly two `operations.AddField` calls and nothing else — no `RunPython`, no `AlterField`, no `RemoveField`.

Tests stay green without applying anything: the test runner builds its own database from the migration files. Do **not** run `manage.py migrate` here — per the Global Constraints, report the generated filename in the task summary and hand the owner the apply/revert commands, then carry on with the code tasks. The live server's batch pages stay broken (`ProgrammingError: column core_stockbatch.price_before does not exist`) until they apply it, which is why Task 9 does the clicking.

- [ ] **Step 6: Run the tests** — same command as Step 3. Expected: the three tests above PASS.

- [ ] **Step 7: Verify nothing else drifted**

Run: `.venv/Scripts/python.exe -B manage.py makemigrations core --check --dry-run --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: exit 0, no "changes detected".
Run: `git status --porcelain core/models.py core/migrations` — expected: only your two paths.

- [ ] **Step 8: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/models.py core/migrations/ core/test_receipt_pricing.py
git commit -m "Give a stock batch the selling price it found and the one it left"
```

---

### Task 2: `ReceiptLine.selling_price` — validated, and inside the fingerprint

**Files:**
- Modify: `core/inventory.py:21-30` (constants + `ReceiptLine`)
- Modify: `core/inventory.py:50-62` (add `_selling_price` next to `_decimal`)
- Modify: `core/inventory.py:130-147` (`_normalize_receipt_lines`)
- Modify: `core/inventory.py:206-213` (`line_data` in the fingerprint payload)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ReceiptLine(product_id, quantity, unit_cost, selling_price=None)`; `MAX_SELLING_PRICE = Decimal("9999.99")`; `_selling_price(value, field_name) -> Decimal | None`. Task 3 reads `line.selling_price`; Task 6 builds these; `core/test_receipt_pricing.py` imports `MAX_SELLING_PRICE`.

- [ ] **Step 1: Run the lane gate** on `core/inventory.py`.

- [ ] **Step 2: Write the failing tests** — append to `core/test_receipt_pricing.py`:

```python
class SellingPriceValidationTests(ReceiptPricingTestCase):
    def test_no_price_means_no_change_and_stays_none(self):
        line = _normalize([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])[0]
        self.assertIsNone(line.selling_price)

    def test_a_zero_price_is_refused_naming_the_line(self):
        with self.assertRaises(ValidationError) as caught:
            self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("0.00"))])
        self.assertEqual(list(caught.exception.error_dict), ["lines[1].selling_price"])

    def test_a_price_above_the_checkout_cap_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("10000.00"))]
            )
        self.assertIn(str(MAX_SELLING_PRICE), caught.exception.messages[0])

    def test_a_price_with_three_decimal_places_is_refused(self):
        with self.assertRaises(ValidationError):
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("19.999"))]
            )

    def test_a_price_is_quantised_to_two_places(self):
        line = _normalize([ReceiptLine(self.product.pk, 4, Decimal("10.00"), "19.9")])[0]
        self.assertEqual(line.selling_price, Decimal("19.90"))

    def test_replaying_a_key_with_a_different_price_is_refused(self):
        key = uuid.uuid4()
        self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))], key=key)
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))],
                key=key,
            )
        self.assertIn("already used for different data", str(caught.exception))

    def test_replaying_a_key_with_the_same_price_returns_the_same_receipt(self):
        key = uuid.uuid4()
        lines = [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))]
        first = self.book(lines, key=key)
        second = self.book(lines, key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(StockReceipt.objects.count(), 1)

    def test_the_service_ceiling_still_refuses_a_five_hundred_and_first_line(self):
        """500 lines is the service's own boundary and it fires before any query;
        the dialog's 50-row cap is a usability limit, not this one."""
        lines = [
            ReceiptLine(self.product.pk, 1, Decimal("1.00"), Decimal("2.00"))
            for _ in range(501)
        ]
        with self.assertRaises(ValidationError) as caught:
            _normalize(lines)
        self.assertIn("500", caught.exception.messages[0])
        self.assertEqual(StockReceipt.objects.count(), 0)
```

Extend the Task 1 import line in `core/test_receipt_pricing.py` (`ValidationError`,
`Product` and the rest already came with Task 1's header):

```python
from core.inventory import (
    MAX_SELLING_PRICE,
    ReceiptLine,
    _normalize_receipt_lines,
    receive_stock,
)
```

and this module-level helper above `ReceiptPricingTestCase`:

```python
def _normalize(lines):
    """The service's own line normalisation, without touching the database."""
    return _normalize_receipt_lines(lines)
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.SellingPriceValidationTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: ERROR at import (`ImportError: cannot import name 'MAX_SELLING_PRICE' from 'core.inventory'`). Add the import back one name at a time if you want to watch the next failure: with `MAX_SELLING_PRICE` still missing, deleting it from the import line instead shows `TypeError: ReceiptLine.__init__() takes 4 positional arguments but 5 were given` — the field does not exist yet. Do not commit either edit.

- [ ] **Step 4: Write the field, the constant and the validator** — in `core/inventory.py`:

```python
MAX_QUANTITY = 2_147_483_647
MAX_RECEIPT_LINES = 500
MAX_MONEY_DIGITS = 10
# checkout refuses any sale line above this (core/checkout.py:157-159), so a
# higher shelf price would book stock the store then cannot sell in one line.
MAX_SELLING_PRICE = Decimal("9999.99")


@dataclass(frozen=True)
class ReceiptLine:
    product_id: UUID
    quantity: int
    unit_cost: Decimal
    selling_price: Decimal | None = None
```

Immediately after `_decimal` (`:62`):

```python
def _selling_price(value, field_name):
    """None means 'change nothing'; it is never read as a zero price."""
    if value is None:
        return None
    amount = _decimal(value, field_name)
    if amount <= 0:
        raise ValidationError({field_name: "Enter a selling price above zero."})
    if amount > MAX_SELLING_PRICE:
        raise ValidationError(
            {field_name: f"The selling price cannot exceed {MAX_SELLING_PRICE}."}
        )
    return amount
```

In `_normalize_receipt_lines`, the `normalized.append(...)` call becomes:

```python
        normalized.append(
            ReceiptLine(
                product_id=_uuid(line.product_id, f"lines[{index}].product_id"),
                quantity=_quantity(line.quantity, f"lines[{index}].quantity"),
                unit_cost=_decimal(line.unit_cost, f"lines[{index}].unit_cost"),
                selling_price=_selling_price(
                    line.selling_price, f"lines[{index}].selling_price"
                ),
            )
        )
```

- [ ] **Step 5: Put the price in the fingerprint payload** — the `line_data` comprehension (`:206-213`) becomes:

```python
    line_data = [
        {
            "product_id": str(line.product_id),
            "quantity": line.quantity,
            "unit_cost": str(line.unit_cost),
            # without this a replay carrying a *different* price would hash
            # identically and be accepted as the same request.
            "selling_price": (
                str(line.selling_price) if line.selling_price is not None else None
            ),
        }
        for line in lines
    ]
```

- [ ] **Step 6: Run the tests** — same command as Step 2's run. Expected: all 8 PASS.

- [ ] **Step 7: Prove no other caller broke** — every existing `ReceiptLine(...)` call passes 3 positional args, so the default keeps them valid. Confirm nothing passes 4 already:

Run: `grep -rn "ReceiptLine(" core --include=*.py | grep -v test_receipt_pricing`
Expected: `core/views.py:487`, `core/views.py:559`, and test files only — each with three arguments.

- [ ] **Step 8: Run the inventory and batch suites**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_inventory core.test_batch_ui --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS (48 + the inventory suite), unchanged.

- [ ] **Step 9: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/inventory.py core/test_receipt_pricing.py
git commit -m "Let a receipt line carry the selling price it will set"
```

---

### Task 3: The service applies the price and records the trail

**Files:**
- Modify: `core/inventory.py:276-309` (`receive_stock`'s batch loop and product write)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: `ReceiptLine.selling_price` (Task 2), `StockBatch.price_before` / `price_applied` (Task 1).
- Produces: the behaviour Tasks 6, 8 and 9 assert — one receipt with N batches, `Product.price` written for priced products only, a per-line trail that chains across lines of the same product.

- [ ] **Step 1: Run the lane gate** on `core/inventory.py`.

- [ ] **Step 2: Write the failing tests** — append:

```python
class PriceWriteTests(ReceiptPricingTestCase):
    def test_three_lines_book_one_receipt_three_batches_and_move_three_shelf_counts(self):
        balm = self.product
        receipt = self.book(
            [
                ReceiptLine(balm.pk, 4, Decimal("10.00")),
                ReceiptLine(self.bottle.pk, 6, Decimal("5.00"), Decimal("9.00")),
                ReceiptLine(balm.pk, 1, Decimal("11.00")),
            ]
        )
        self.assertEqual(StockReceipt.objects.count(), 1)
        batches = list(StockBatch.objects.filter(receipt=receipt).order_by("line_number"))
        self.assertEqual([b.line_number for b in batches], [1, 2, 3])
        self.assertEqual([b.quantity_received for b in batches], [4, 6, 1])
        balm.refresh_from_db()
        self.bottle.refresh_from_db()
        self.assertEqual((balm.stock, balm.cost), (5, Decimal("11.00")))
        self.assertEqual((self.bottle.stock, self.bottle.price), (9, Decimal("9.00")))

    def test_a_priceless_line_leaves_both_trail_columns_null(self):
        receipt = self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertIsNone(batch.price_before)
        self.assertIsNone(batch.price_applied)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))

    def test_a_priced_line_writes_the_price_and_chains_the_trail(self):
        receipt = self.book(
            [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))]
        )
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertEqual(batch.price_before, Decimal("18.00"))
        self.assertEqual(batch.price_applied, Decimal("20.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("20.00"))

    def test_the_second_priced_line_of_a_product_starts_where_the_first_ended(self):
        receipt = self.book(
            [
                ReceiptLine(self.product.pk, 2, Decimal("10.00"), Decimal("20.00")),
                ReceiptLine(self.product.pk, 3, Decimal("12.00"), Decimal("25.00")),
            ]
        )
        first, second = StockBatch.objects.filter(receipt=receipt).order_by("line_number")
        self.assertEqual(
            (first.price_before, first.price_applied), (Decimal("18.00"), Decimal("20.00"))
        )
        self.assertEqual(
            (second.price_before, second.price_applied), (Decimal("20.00"), Decimal("25.00"))
        )
        self.product.refresh_from_db()
        self.assertEqual((self.product.price, self.product.cost), (Decimal("25.00"), Decimal("12.00")))

    def test_a_priced_line_leaves_unpriced_products_prices_alone(self):
        self.book(
            [
                ReceiptLine(self.product.pk, 2, Decimal("10.00"), Decimal("22.00")),
                ReceiptLine(self.bottle.pk, 2, Decimal("5.00")),
            ]
        )
        self.bottle.refresh_from_db()
        self.assertEqual(self.bottle.price, Decimal("7.50"))

    def test_the_applied_price_is_the_one_checkout_charges(self):
        self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))])
        # the cart still holds the OLD price: the register is refused, not re-priced
        with self.assertRaises(ValidationError) as caught:
            checkout(
                actor=self.admin,
                request_key=uuid.uuid4(),
                lines=[SaleLine(self.product.pk, 2, Decimal("36.00"))],
            )
        self.assertIn("The cart price changed", str(caught.exception))
        checkout(
            actor=self.admin,
            request_key=uuid.uuid4(),
            lines=[SaleLine(self.product.pk, 2, Decimal("40.00"))],
        )

    def test_one_bad_line_among_three_leaves_no_receipt_no_batch_and_no_price(self):
        self.product.refresh_from_db()
        before = (StockReceipt.objects.count(), StockBatch.objects.count(), self.product.price)
        with self.assertRaises(ValidationError):
            self.book(
                [
                    ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00")),
                    ReceiptLine(self.bottle.pk, 6, Decimal("5.00")),
                    ReceiptLine(self.product.pk, 1, Decimal("11.00"), Decimal("0.00")),
                ]
            )
        self.product.refresh_from_db()
        self.assertEqual(
            before, (StockReceipt.objects.count(), StockBatch.objects.count(), self.product.price)
        )

    def test_a_drift_on_the_third_product_refuses_the_whole_receipt(self):
        Product.objects.filter(pk=self.bottle.pk).update(stock=99)
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [
                    ReceiptLine(self.product.pk, 4, Decimal("10.00")),
                    ReceiptLine(self.bottle.pk, 6, Decimal("5.00"), Decimal("9.00")),
                ]
            )
        self.assertIn(self.bottle.name, str(caught.exception))
        self.assertEqual(StockReceipt.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.PriceWriteTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: FAIL — the priced-line tests show `price_before`/`price_applied` still `None` and `Product.price` unmoved; the two all-or-none tests pass already (the transaction is already atomic) — that is expected, they are the guard the refactor must not break.

- [ ] **Step 4: Write the trail per line** — in `receive_stock`, replace the batch loop (currently `:276-295`) with:

```python
        quantities = {product_id: 0 for product_id in product_ids}
        last_cost = {}
        last_price = {}
        price_in_force = {}
        batches = []
        estimated = source != StockReceiptSource.PURCHASE
        for line_number, line in enumerate(lines, start=1):
            product = products[line.product_id]
            quantities[line.product_id] += line.quantity
            last_cost[line.product_id] = line.unit_cost
            batch = StockBatch(
                receipt=receipt,
                product=product,
                line_number=line_number,
                quantity_received=line.quantity,
                quantity_remaining=line.quantity,
                unit_cost=line.unit_cost,
                cost_is_estimated=estimated,
            )
            if line.selling_price is not None:
                # "the price this line found" is the price the *previous line of
                # this product* left behind, not the one read at the top of the
                # transaction: the trail has to chain, or a two-line re-price
                # reports the same starting price twice.
                batch.price_before = price_in_force.get(line.product_id, product.price)
                batch.price_applied = line.selling_price
                price_in_force[line.product_id] = line.selling_price
                last_price[line.product_id] = line.selling_price
            batches.append(batch)
        StockBatch.objects.bulk_create(batches)
```

- [ ] **Step 5: Push the price out to the product** — the write loop and `bulk_update` (currently `:297-309`) become:

```python
        for product_id, product in products.items():
            new_stock = product.stock + quantities[product_id]
            if new_stock > MAX_QUANTITY:
                raise ValidationError({"lines": f"Stock exceeds the limit for {product.name}."})
            product.stock = new_stock
            if source == StockReceiptSource.PURCHASE:
                product.cost = last_cost[product_id]
            # unlike cost, price applies from every source: an owner who typed a
            # price on an OPENING or ADJUSTMENT line meant the price, not the cost.
            if product_id in last_price:
                product.price = last_price[product_id]
            product.updated = timezone.now()
        # "price" joins the list only when some line carried one. When it does,
        # bulk_update also rewrites the stored price for products this receipt
        # did not re-price -- the row locks are held from the read to here, so
        # that write is the value that was already in the column.
        changed_fields = ["stock", "cost", "updated"]
        if last_price:
            changed_fields.append("price")
        Product.objects.bulk_update(
            products.values(),
            changed_fields,
            batch_size=len(products),
        )
        return receipt
```

- [ ] **Step 6: Run the tests** — same command as Step 2. Expected: all 8 PASS.

- [ ] **Step 7: Run the suites this touches**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_inventory core.test_batch_ui core.test_receipt_pricing --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS. `core.test_inventory` is the one that would notice a `ReceiptLine` or fingerprint change it disagrees with; if it fails, read the failure before touching that file — it is the other lane's, and a fingerprint change legitimately alters any test that pins a literal hash.

- [ ] **Step 8: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/inventory.py core/test_receipt_pricing.py
git commit -m "Apply a receipt line's selling price store-wide and keep the trail"
```

---

### Task 4: The picker — one ADMIN-only product search that returns options

**Files:**
- Modify: `core/batch_views.py:8-33` (imports) and the end of the view block
- Modify: `core/urls.py:72-77` (the receipts routes in the products include)
- Create: `core/templates/core/products/partials/receipt_product_options.html`
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: `Product`, `is_admin`, the expression `Q(name__icontains) | Q(sku__icontains)` copied from `core/views.py:1165-1166`.
- Produces: URL name `core:receipt-product-options` (GET, `?q=`), `RECEIPT_SEARCH_RESULTS = 20`, the fragment whose buttons carry `data-product-id|name|sku|cost|price|stock` and `@click="pickReceiptProduct($el)"`. Task 5's row partial targets it; Task 7's dialog provides the Alpine scope.

- [ ] **Step 1: Run the lane gate** on `core/urls.py`. `core/batch_views.py` is this lane's file, but check it is unmodified by the other session too: `git status --porcelain core/batch_views.py core/templates/core/products` must be empty.

- [ ] **Step 2: Write the failing tests** — append:

```python
class ReceiptProductSearchTests(ReceiptPricingTestCase):
    def url(self):
        return reverse("core:receipt-product-options")

    def test_the_search_finds_by_name_and_by_sku(self):
        for term in ("Shea", "SHB01"):
            response = self.client.get(self.url(), {"q": term})
            self.assertEqual(response.status_code, 200, term)
            self.assertContains(response, 'data-product-name="Shea Repair Balm"')
            self.assertNotContains(response, "Bottle Gargle")

    def test_a_blank_term_still_offers_the_first_products(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Shea Repair Balm")

    def test_no_match_says_so_instead_of_returning_an_empty_box(self):
        response = self.client.get(self.url(), {"q": "zzz-nothing"})
        self.assertContains(response, "Nothing in the catalogue matches")

    def test_the_list_is_capped_at_twenty_products(self):
        for index in range(25):
            Product.objects.create(
                name=f"Cap filler {index}", stock=1, cost=Decimal("1.00"),
                price=Decimal("2.00"), profit_rate=Decimal("0.50"),
            )
        html = self.client.get(self.url(), {"q": "Cap filler"}).content.decode()
        self.assertEqual(
            sum(
                1
                for _tag, attributes in self.elements_with_attributes(html)
                if "data-product-id" in attributes
            ),
            20,
        )

    def test_the_cashier_and_the_anonymous_visitor_are_turned_away(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_a_product_name_never_reaches_a_js_attribute(self):
        """Names belong in data-*, because a name is exactly what breaks a JS literal."""
        awkward = Product.objects.create(
            name='O\'Neil "Reserve" Balm', sku="ONE1", stock=1,
            cost=Decimal("1.00"), price=Decimal("2.00"), profit_rate=Decimal("0.50"),
        )
        response = self.client.get(self.url(), {"q": "Reserve"})
        html = response.content.decode()
        for _tag, attributes in self.elements_with_attributes(html):
            for name, value in attributes.items():
                if name.startswith(self.JS_ATTRIBUTE_PREFIXES):
                    self.assertNotIn("Reserve", value)
        # html.parser unescapes attribute values, so this is what the DOM sees:
        # the name verbatim, quotes and all -- inside data-*, never a directive.
        self.assertEqual(
            [
                attributes["data-product-name"]
                for _tag, attributes in self.elements_with_attributes(html)
                if "data-product-name" in attributes
            ],
            [awkward.name],
        )
        compile_js(self, html, **{"@click": "alpine"})
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptProductSearchTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: ERROR — `NoReverseMatch: 'receipt-product-options'`.

- [ ] **Step 4: Add the imports and the constant** to `core/batch_views.py`:

```python
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
```

and, under `BATCH_VALUE`:

```python
# the picker returns a page of options, not a catalogue: twenty is what a
# dialog's dropdown can be scanned without the owner scrolling.
RECEIPT_SEARCH_RESULTS = 20
```

- [ ] **Step 5: Add the view** at the end of `core/batch_views.py`:

```python
@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_product_options(request):
    """The receipt dialog's picker: selectable options, never a ledger row.

    ``load_products`` is not reusable -- it renders table rows for the ledger.
    The filter is copied from the one the ledger itself runs
    (core/views.py:1163-1167) so a name and a code search identically in both,
    and an empty term still answers (the dialog offers something to click).
    """
    term = request.GET.get("q", "").strip()
    products = Product.objects.all()
    if term:
        products = products.filter(
            Q(name__icontains=term) | Q(sku__icontains=term)
        ).order_by("name")
    else:
        products = products.order_by("name")
    return render(
        request,
        "core/products/partials/receipt_product_options.html",
        {"products": products[:RECEIPT_SEARCH_RESULTS], "term": term},
    )
```

- [ ] **Step 6: Add the route** — in `core/urls.py`, inside the products include, **before** `receipts/<uuid:receipt_id>/` so the literal segment is matched first and the uuid converter never has to reject it:

```python
                path("receipts/", batch_views.stock_receipts, name="stock-receipts"),
                path(
                    "receipts/product-search/",
                    batch_views.receipt_product_options,
                    name="receipt-product-options",
                ),
```

Task 5 adds the dialog's two routes in the same block, in front of this one.

- [ ] **Step 7: Create the fragment** `core/templates/core/products/partials/receipt_product_options.html`:

```html
{% load humanize %}
{% load icons %}
{% comment %}
  One line per candidate product, as a button the dialog's pickReceiptProduct()
  reads. Everything the row needs comes from data-product-* and out of
  $el.dataset: a catalogue name is the one string that can break a JS literal,
  so it is never interpolated into @click, hx-* or x-*.
  This fragment carries no Alpine scope of its own: htmx swaps it inside the
  dialog form, which owns the x-data.
{% endcomment %}
{% for product in products %}
  <button type="button"
          class="receipt-picker-option flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-emerald-50 dark:text-slate-200 dark:hover:bg-emerald-950/40"
          data-product-id="{{ product.pk }}"
          data-product-name="{{ product.name }}"
          data-product-sku="{{ product.sku|default:'No code' }}"
          data-product-cost="{{ product.cost }}"
          data-product-price="{{ product.price }}"
          data-product-stock="{{ product.stock }}"
          @click="pickReceiptProduct($el)">
    <span class="min-w-0">
      <span class="block truncate font-medium">{{ product.name }}</span>
      <span class="tnum block text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {{ product.sku|default:"No code" }} · {{ product.stock|intcomma }} on shelf
      </span>
    </span>
    <span class="tnum shrink-0 text-xs font-semibold">GH₵ {{ product.price|floatformat:2|intcomma }}</span>
  </button>
{% empty %}
  <p class="px-3 py-4 text-center text-xs text-slate-500 dark:text-slate-400">
    {% if term %}
      Nothing in the catalogue matches {{ term }}.
    {% else %}
      The catalogue has no products to add yet.
    {% endif %}
  </p>
{% endfor %}
```

- [ ] **Step 8: Build and run**

Run: `npm run build` — expected: icons exit 0 (no new icon name used) and Tailwind regenerates.
Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptProductSearchTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: all 6 PASS.

- [ ] **Step 9: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/batch_views.py core/urls.py core/templates/core/products/partials/ core/test_receipt_pricing.py static/src/output.css
git commit -m "Search the catalogue as picker options for a receipt line"
```

---

### Task 5: The line partial, the blank-line endpoint, and the dialog that opens

**Files:**
- Create: `core/templates/core/products/partials/receipt_line_row.html`
- Create: `core/templates/core/products/modals/receive_stock.html`
- Modify: `core/batch_views.py` (constants, `receive_stock_question` GET, `receipt_line_blank`)
- Modify: `core/urls.py` (the dialog's two routes, in front of the picker route)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: `core:receipt-product-options` (Task 4), and `partials/modal.html` — the shell at **`templates/partials/modal.html`** (project-level templates dir, not `core/templates/`), whose blocks this dialog fills: `modal_width`, `modal_icon`, `modal_title`, `modal_subtitle`, `dialog_attrs`, `modal_body`, `modal_footer`. `dialog_attrs` lands on the div that wraps both body and footer, so the `x-data` scope covers the rows, the summary and the submit button; `[data-modal-close]` and `[data-autofocus]` are honoured by the controller in `products.html:91-198`.
- Produces: URL names `core:receive-stock-question` (GET opens, `?product_id=` prefills) and `core:receipt-line-blank` (GET one empty row); `MAX_RECEIPT_LINE_UNITS = 100_000`, `MAX_RECEIPT_DIALOG_ROWS = 50`, `RECEIPT_UNIT_PRESETS = (12, 24, 48, 100)`; `_line_context()`; the row's posted names `line_product_id[]`, `line_units[]`, `line_unit_cost[]`, `line_selling_price[]`; the Alpine method names `syncReceipt`, `pickReceiptProduct`, `removeReceiptLine`, `setReceiptUnits` and the element classes `.receipt-row`, `.receipt-row-product-id`, `.receipt-row-search`, `.receipt-row-picker`, `.receipt-row-units`, `.receipt-row-cost`, `.receipt-row-price`, `.receipt-row-below-cost`, `.receipt-row-over-cap`, `.receipt-summary-*`. Task 6 consumes all of these; Task 7 wires the entry points.

- [ ] **Step 1: Run the lane gate** on `core/batch_views.py`, `core/urls.py`, `core/templates/core/products`.

- [ ] **Step 2: Write the failing tests** — append:

```python
class ReceiptDialogTests(ReceiptPricingTestCase):
    def dialog(self, product_id=None):
        url = reverse("core:receive-stock-question")
        if product_id:
            url = f"{url}?product_id={product_id}"
        return self.client.get(url)

    def test_opening_the_dialog_seeds_one_blank_line(self):
        response = self.dialog()
        html = response.content.decode()
        self.assertEqual(html.count('class="receipt-row '), 1)
        for name in ("line_product_id[]", "line_units[]", "line_unit_cost[]",
                     "line_selling_price[]"):
            self.assertIn(f'name="{name}"', html)
        self.assertIn('name="request_key"', html)
        self.assertEqual(html.count("data-autofocus"), 1)

    def test_a_product_id_prefers_that_product_and_says_so(self):
        html = self.dialog(self.bottle.pk).content.decode()
        self.assertIn("Bottle Gargle", html)
        self.assertEqual(html.count("data-autofocus"), 1)
        self.assertEqual(html.count('class="receipt-row '), 1)
        # the search box is answered, so focus must sit further along the row
        searches = [
            attributes
            for _tag, attributes in self.elements_with_attributes(html)
            if "receipt-row-search" in attributes.get("class", "")
        ]
        self.assertEqual(len(searches), 1)
        self.assertNotIn("data-autofocus", searches[0])

    def test_the_prefill_defaults_cost_from_the_catalogue_and_leaves_price_blank(self):
        response = self.dialog(self.bottle.pk)
        self.assertContains(response, 'value="4.00"')
        self.assertContains(response, 'placeholder="no change"')
        self.assertContains(response, f'value="{self.bottle.pk}"')

    def test_an_unresolvable_product_id_still_opens_a_blank_dialog(self):
        response = self.dialog(uuid.uuid4())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Bottle Gargle", response.content.decode())

    def test_the_dialog_carries_exactly_one_parseable_x_data(self):
        html = self.dialog().content.decode()
        scopes = self.attribute_values(html, "x-data")
        self.assertEqual(len(scopes), 1, "a dialog with two Alpine scopes has two ideas about the rows")
        compile_js(self, html, **{"x-data": "expression"})

    def test_no_js_attribute_carries_a_raw_double_quote(self):
        html = self.dialog().content.decode()
        for _tag, attributes in self.elements_with_attributes(html):
            for name, value in attributes.items():
                if name.startswith(self.JS_ATTRIBUTE_PREFIXES):
                    self.assertNotIn('"', value, f"{name} would close its own attribute")

    def test_every_handler_compiles_with_the_library_that_binds_it(self):
        """htmx binds 'event', Alpine binds '$event' -- mixing them is a ReferenceError."""
        html = self.dialog().content.decode()
        compile_js(
            self,
            html,
            **{
                "@click": "alpine",
                "@input": "alpine",
                "x-text": "expression",
                "x-show": "expression",
                "x-init": "expression",
                "hx-on::after-request": "htmx",
            },
        )

    def test_the_blank_line_endpoint_returns_one_row_with_no_product(self):
        response = self.client.get(reverse("core:receipt-line-blank"))
        html = response.content.decode()
        self.assertEqual(html.count('class="receipt-row '), 1)
        self.assertIn('name="line_product_id[]"', html)
        self.assertIn('value=""', html)
        self.assertContains(response, "Name or code")

    def test_the_cashier_cannot_open_either_endpoint(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.dialog().status_code, 302)
        self.assertEqual(
            self.client.get(reverse("core:receipt-line-blank")).status_code, 302
        )
```

The row partial renders a `<div>` grid, not a table, so the base class's
`tbody_rows` cannot see a row — which is why these tests assert on rendered
attribute values and text rather than on cell positions. Task 8, where the
surfaces *are* tables, goes back to position pinning.

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptDialogTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: ERROR — `NoReverseMatch: 'receive-stock-question'`.

- [ ] **Step 4: Add the dialog constants and the line context** to `core/batch_views.py`:

```python
# was core/views.MAX_RESTOCK_UNITS: a per-line input ceiling for the dialog, not
# a service rule -- the service's own ceilings stay MAX_QUANTITY / MAX_RECEIPT_LINES.
MAX_RECEIPT_LINE_UNITS = 100_000
MAX_RECEIPT_DIALOG_ROWS = 50
RECEIPT_UNIT_PRESETS = (12, 24, 48, 100)


def _line_context(product_id="", product=None, units="", unit_cost="", selling_price="", error=False):
    """One receipt line as the row partial reads it: flat, all keys present.

    The partial is the only renderer for a row -- GET, failed POST and the
    blank-line endpoint all pass this dict -- so a row cannot look different
    depending on which of the three built it.
    """
    return {
        "product_id": product_id,
        "product": product,
        "units": units,
        "unit_cost": unit_cost,
        "selling_price": selling_price,
        "error": error,
    }


def _dialog_context(request, *, lines=None, request_key="", message=""):
    return {
        "lines": lines if lines is not None else [_line_context()],
        "request_key": request_key,
        "message": message,
        "max_units": MAX_RECEIPT_LINE_UNITS,
        "max_rows": MAX_RECEIPT_DIALOG_ROWS,
        "price_cap": MAX_SELLING_PRICE,
        "presets": RECEIPT_UNIT_PRESETS,
    }
```

and the import at the top of the module (`batch_views.py` reaches into the
service layer for the first time here; Task 6 extends the same line):

```python
from core.inventory import MAX_SELLING_PRICE
```

- [ ] **Step 5: Add the two GET views**:

```python
@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_line_blank(request):
    """One empty line, swapped into the open dialog by 'Add another product'."""
    return render(
        request,
        "core/products/partials/receipt_line_row.html",
        {"line": _line_context(), "max_units": MAX_RECEIPT_LINE_UNITS,
         "presets": RECEIPT_UNIT_PRESETS},
    )


@login_required
@user_passes_test(is_admin)
def receive_stock_question(request):
    """Book one delivery, however many products it carried."""
    if request.method == "POST":
        return _book_receipt(request)
    lines = [_line_context()]
    raw_product_id = request.GET.get("product_id")
    if raw_product_id:
        product = Product.objects.filter(pk=raw_product_id).first()
        if product is not None:
            lines = [
                _line_context(
                    product_id=str(product.pk),
                    product=product,
                    units=RECEIPT_UNIT_PRESETS[1],
                    unit_cost=product.cost,
                )
            ]
        # a product that is gone leaves a blank dialog rather than a 404: the
        # dialog is for the delivery, and the owner can still book the rest of it.
    return render(request, "core/products/modals/receive_stock.html", _dialog_context(request, lines=lines))
```

Note `@require_GET` is deliberately absent on `receive_stock_question` — it is the POST target too (Task 6), and the repo's write views (`restock_product`, `add_product`) answer both.

- [ ] **Step 5b: Add the dialog's two routes** in `core/urls.py`, in the products include, above the picker route Task 4 added:

```python
                path(
                    "receipts/receive/",
                    batch_views.receive_stock_question,
                    name="receive-stock-question",
                ),
                path(
                    "receipts/receive/line/",
                    batch_views.receipt_line_blank,
                    name="receipt-line-blank",
                ),
```

- [ ] **Step 6: Create the row partial** `core/templates/core/products/partials/receipt_line_row.html`:

```html
{% load humanize %}
{% load icons %}
{% comment %}
  One receipt line. The only renderer for a row: the dialog's GET, the dialog's
  failure re-render and the blank-line endpoint all include this with a
  _line_context() dict, so a posted line and a fresh one are the same markup.

  The picker div MUST stay the element immediately after the search input: the
  search targets it with hx-target="next .receipt-row-picker", which walks
  following siblings. Every value the dialog's JS reads comes off a class, never
  off [name="..."], because a quoted attribute selector would need a double
  quote inside a double-quoted attribute.

  is_first is only ever true for the dialog's first row (the blank-line endpoint
  renders without it). products.html:201 focuses the overlay's first
  [data-autofocus], so exactly one input carries it: the search box for a row
  still looking for a product, the units box once one is chosen.
{% endcomment %}
<div class="receipt-row flex flex-col gap-2 rounded-lg border bg-white p-3 shadow-sm dark:bg-slate-900 {% if line.error %}border-rose-400 ring-2 ring-rose-200 dark:ring-rose-900{% else %}border-slate-200 dark:border-slate-700{% endif %} sm:grid sm:grid-cols-12 sm:items-start sm:gap-3">
  <div class="min-w-0 sm:col-span-5">
    <p class="receipt-row-chosen truncate text-sm font-semibold text-slate-900 dark:text-slate-100 {% if not line.product %}hidden{% endif %}">
      {{ line.product.name }}
      <span class="receipt-row-chosen-sku tnum ml-1 text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 {% if not line.product %}hidden{% endif %}">
        {{ line.product.sku|default:"No code" }}
      </span>
    </p>
    <input type="hidden"
           name="line_product_id[]"
           class="receipt-row-product-id"
           value="{{ line.product_id }}">
    <input type="search"
           autocomplete="off"
           name="q"
           class="receipt-row-search w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
           placeholder="Name or code"
           aria-label="Find a product for this line"
           {% if is_first and not line.product %}data-autofocus{% endif %}
           hx-get="{% url 'core:receipt-product-options' %}"
           hx-trigger="keyup changed delay:300ms"
           hx-target="next .receipt-row-picker"
           hx-swap="innerHTML">
    <div class="receipt-row-picker mt-1 max-h-56 overflow-y-auto rounded-lg bg-slate-50 empty:hidden dark:bg-slate-950/60"></div>
  </div>
  <input type="number"
         name="line_units[]"
         min="1"
         step="1"
         class="receipt-row-units tnum rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm font-semibold text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 sm:col-span-2"
         placeholder="Units"
         aria-label="Units for this line"
         {% if is_first and line.product %}data-autofocus{% endif %}
         max="{{ max_units }}"
         value="{{ line.units }}"
         @input="syncReceipt()">
  <div class="sm:col-span-2">
    <input type="number"
           name="line_unit_cost[]"
           min="0"
           step="0.01"
           class="receipt-row-cost tnum w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
           placeholder="Unit cost"
           aria-label="Unit cost for this line"
           value="{{ line.unit_cost }}"
           @input="syncReceipt()">
  </div>
  <div class="sm:col-span-2">
    <input type="number"
           name="line_selling_price[]"
           min="0.01"
           step="0.01"
           class="receipt-row-price tnum w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
           placeholder="no change"
           aria-label="New selling price for this line, blank to leave it"
           value="{{ line.selling_price }}"
           @input="syncReceipt()">
  </div>
  <button type="button"
          class="flex h-8 w-8 shrink-0 items-center justify-center self-start rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/60 sm:col-span-1 sm:justify-self-end"
          title="Remove this line"
          @click="removeReceiptLine($el)">
    {% icon 'delete' 'text-[18px]' %}
    <span class="sr-only">Remove this line</span>
  </button>
  <div class="flex flex-wrap items-center gap-2 text-[11px] sm:col-span-12">
    <span class="flex items-center gap-1">
      {% for preset in presets %}
        <button type="button"
                class="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                data-preset="{{ preset }}"
                @click="setReceiptUnits($el)">+{{ preset }}</button>
      {% endfor %}
    </span>
    <span class="receipt-row-below-cost hidden rounded-full bg-rose-100 px-2 py-0.5 font-semibold uppercase text-rose-700 dark:bg-rose-950/60 dark:text-rose-400">below cost</span>
    <span class="receipt-row-over-cap hidden rounded-full bg-amber-100 px-2 py-0.5 font-semibold uppercase text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">over the sellable cap</span>
  </div>
</div>
```

- [ ] **Step 7: Create the dialog** `core/templates/core/products/modals/receive_stock.html`. The request-key IIFE is copied verbatim from `restock_product.html:16-32` — same body, same escaping, and `requestKey: '{{ request_key }}' ||` in front of it so a corrected resubmission reuses the posted key:

```html
{% extends "partials/modal.html" %}
{% load humanize %}
{% load icons %}
{% block modal_width %}max-w-4xl{% endblock modal_width %}
{% block modal_icon %}{% icon 'inventory_2' 'text-[24px]' %}{% endblock modal_icon %}
{% block modal_title %}Receive Delivery{% endblock modal_title %}
{% block modal_subtitle %}Book one delivery, as many products as it carried.{% endblock modal_subtitle %}
{% block dialog_attrs %}
  x-data="{
    maxRows: {{ max_rows }},
    maxUnits: {{ max_units }},
    priceCap: {{ price_cap }},
    rowCount: {{ lines|length }},
    emptyRows: 0,
    requestKey: '{{ request_key }}' || (function () {
      var api = window.crypto;
      if (api &amp;&amp; typeof api.randomUUID === 'function') {
        try {
          return api.randomUUID();
        } catch (err) {
          /* plain http over the LAN: crypto.randomUUID is unavailable, so the key is built below */
        }
      }
      var digits = [];
      for (var i = 0; i &lt; 32; i++) {
        digits.push(Math.floor(Math.random() * 16).toString(16));
      }
      digits[12] = '4';
      digits[16] = ['8', '9', 'a', 'b'][Math.floor(Math.random() * 4)];
      return digits.slice(0, 8).join('') + '-' + digits.slice(8, 12).join('') + '-' + digits.slice(12, 16).join('') + '-' + digits.slice(16, 20).join('') + '-' + digits.slice(20, 32).join('');
    })(),
    num(value) {
      const parsed = parseFloat(value);
      return isNaN(parsed) ? 0 : parsed;
    },
    money(value) {
      return this.num(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    rowEls() {
      return Array.from(this.$el.querySelectorAll('.receipt-row'));
    },
    set(selector, text) {
      this.$el.querySelector(selector).textContent = text;
    },
    setReceiptUnits($el) {
      const row = $el.closest('.receipt-row');
      row.querySelector('.receipt-row-units').value = $el.dataset.preset;
      this.syncReceipt();
    },
    pickReceiptProduct($el) {
      const row = $el.closest('.receipt-row');
      row.querySelector('.receipt-row-product-id').value = $el.dataset.productId;
      const title = row.querySelector('.receipt-row-chosen');
      title.textContent = $el.dataset.productName;
      title.classList.remove('hidden');
      const sku = row.querySelector('.receipt-row-chosen-sku');
      sku.textContent = $el.dataset.productSku;
      sku.classList.remove('hidden');
      const cost = row.querySelector('.receipt-row-cost');
      if (cost.value === '') {
        cost.value = $el.dataset.productCost;
      }
      row.querySelector('.receipt-row-search').value = '';
      row.querySelector('.receipt-row-picker').innerHTML = '';
      this.syncReceipt();
    },
    removeReceiptLine($el) {
      if (this.rowEls().length > 1) {
        $el.closest('.receipt-row').remove();
      }
      this.syncReceipt();
    },
    syncReceipt() {
      const rows = this.rowEls();
      let units = 0;
      let cost = 0;
      let retail = 0;
      let priced = 0;
      let empty = 0;
      rows.forEach((row) => {
        const parsed = parseInt(row.querySelector('.receipt-row-units').value, 10);
        const qty = isNaN(parsed) || parsed &lt; 1 ? 0 : parsed;
        const lineCost = this.num(row.querySelector('.receipt-row-cost').value);
        const priceInput = row.querySelector('.receipt-row-price');
        const changed = priceInput.value !== '';
        const each = changed ? this.num(priceInput.value) : lineCost;
        row.querySelector('.receipt-row-below-cost').classList.toggle(
          'hidden',
          !(changed &amp;&amp; each &lt; lineCost)
        );
        row.querySelector('.receipt-row-over-cap').classList.toggle(
          'hidden',
          !(changed &amp;&amp; each > this.priceCap)
        );
        if (!row.querySelector('.receipt-row-product-id').value) {
          empty += 1;
        }
        units += qty;
        cost += qty * lineCost;
        retail += qty * each;
        priced += changed ? 1 : 0;
      });
      this.rowCount = rows.length;
      this.emptyRows = empty;
      this.set('.receipt-summary-units', units.toLocaleString('en-US'));
      this.set('.receipt-summary-cost', this.money(cost));
      this.set('.receipt-summary-retail', this.money(retail));
      const margin = retail &lt;= 0 ? '0.0' : (((retail - cost) / retail) * 100).toFixed(1);
      this.set('.receipt-summary-margin', (retail &gt; 0 &amp;&amp; retail - cost >= 0 ? '+' : '') + margin + '%');
      this.set('.receipt-summary-lines', String(rows.length));
      this.set('.receipt-summary-priced', String(priced));
    },
  }"
  x-init="syncReceipt()"
{% endblock dialog_attrs %}
{% block modal_body %}
  <form id="receive-form"
        class="flex flex-col gap-4"
        hx-post="{% url 'core:receive-stock-question' %}"
        hx-target="#modal_root"
        hx-swap="innerHTML">
    {% if message %}
      <p role="alert"
         class="rounded-lg bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
        Nothing was saved. {{ message }}
      </p>
    {% endif %}
    <input type="hidden" name="request_key" :value="requestKey">
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <label class="flex flex-col gap-1">
        <span class="text-xs font-semibold uppercase tracking-wide text-slate-700 dark:text-slate-200">Purchased on</span>
        <input name="purchased_on"
               type="date"
               value="{{ posted_purchased_on }}"
               class="tnum w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-semibold uppercase tracking-wide text-slate-700 dark:text-slate-200">Supplier</span>
        <input name="supplier_name"
               type="text"
               maxlength="255"
               value="{{ posted_supplier_name }}"
               placeholder="Who sold it to you"
               class="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-semibold uppercase tracking-wide text-slate-700 dark:text-slate-200">Invoice / reference</span>
        <input name="external_reference"
               type="text"
               maxlength="255"
               value="{{ posted_external_reference }}"
               placeholder="INV-0000"
               class="tnum w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
      </label>
    </div>

    <div class="flex flex-col gap-2">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-200">Lines</span>
        <button type="button"
                hx-get="{% url 'core:receipt-line-blank' %}"
                hx-target="#receipt_lines"
                hx-swap="beforeend"
                hx-on::after-request="syncReceipt()"
                :disabled="rowCount >= maxRows"
                :class="rowCount >= maxRows ? 'cursor-not-allowed bg-slate-200 text-slate-400 dark:bg-slate-800' : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-950/60 dark:text-emerald-300'"
                class="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-semibold transition-colors dark:border-emerald-900">
          {% icon 'add' 'text-[16px]' %}
          <span>Add another product</span>
        </button>
      </div>
      <div id="receipt_lines" class="flex flex-col gap-2">
        {% for line in lines %}
          {% include "core/products/partials/receipt_line_row.html" with line=line presets=presets max_units=max_units is_first=forloop.first %}
        {% endfor %}
      </div>
      <p class="text-[11px] text-slate-500 dark:text-slate-400">
        A blank selling price leaves that product's price where it is.
        <span x-show="emptyRows > 0" class="font-semibold text-rose-600 dark:text-rose-400">Every line needs a product.</span>
        <span class="receipt-summary-lines-note text-amber-700 dark:text-amber-400" x-show="rowCount >= maxRows">
          This dialog stops at <span class="tnum">{{ max_rows }}</span> lines; book the rest as a second receipt.
        </span>
      </p>
    </div>

    <div class="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/40">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2 dark:border-slate-800">
        <span class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-200">
          {% icon 'insights' 'text-[18px] text-emerald-700 dark:text-emerald-400' %}
          Calculation &amp; Ledger Impact
        </span>
        <span class="rounded-full px-2 py-0.5 text-[11px] font-semibold text-slate-600 dark:text-slate-300">
          <span class="receipt-summary-lines tnum">0</span> line(s) on this receipt
        </span>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="flex flex-col">
          <span class="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Units in</span>
          <span class="receipt-summary-units tnum mt-0.5 text-base font-semibold text-slate-900 dark:text-slate-100">0</span>
        </div>
        <div class="flex flex-col">
          <span class="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Delivery cost</span>
          <span class="mt-0.5 text-base font-semibold text-slate-900 dark:text-slate-100">
            GH₵ <span class="receipt-summary-cost tnum">0.00</span>
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Retail at these prices</span>
          <span class="mt-0.5 text-base font-semibold text-slate-900 dark:text-slate-100">
            GH₵ <span class="receipt-summary-retail tnum">0.00</span>
          </span>
        </div>
        <div class="flex flex-col">
          <span class="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Gross margin</span>
          <span class="receipt-summary-margin tnum mt-0.5 text-base font-semibold text-emerald-700 dark:text-emerald-400">+0.0%</span>
        </div>
      </div>
      <p class="text-[11px] text-slate-500 dark:text-slate-400">
        <span class="receipt-summary-priced tnum font-semibold">0</span> line(s) will change a store-wide selling price.
      </p>
    </div>
  </form>
{% endblock modal_body %}
{% block modal_footer %}
  <button type="button"
          data-modal-close
          class="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100">
    Cancel
  </button>
  <button type="submit"
          form="receive-form"
          :disabled="emptyRows > 0 || rowCount === 0"
          :class="emptyRows > 0 || rowCount === 0 ? 'cursor-not-allowed bg-slate-400 text-white dark:bg-slate-700 dark:text-slate-400' : 'bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-500 dark:text-slate-950 dark:hover:bg-emerald-400'"
          class="inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold text-white transition-colors">
    {% icon 'check_circle' 'text-[18px]' %}
    <span x-text="'Book ' + rowCount + (rowCount === 1 ? ' line' : ' lines')">Book 1 line</span>
  </button>
{% endblock modal_footer %}
```

The `{{ posted_purchased_on }}` / `{{ posted_supplier_name }}` / `{{ posted_external_reference }}` variables come from Task 6's `_dialog_context`; until then they render empty, which is correct for a GET.

- [ ] **Step 8: Add the Alpine-scope note to `receipt_product_options.html`.** The fragment's `@click` is `pickReceiptProduct($el)`, which Task 5 defines on the dialog scope — the fragment is only ever swapped inside that form. Add one line to its `{% comment %}` block: `Chosen by the dialog's pickReceiptProduct(); the fragment has no scope of its own.`

- [ ] **Step 9: Build and run**

Run: `npm run build`
Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptDialogTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: all 9 PASS. `test_every_handler_compiles_with_the_library_that_binds_it` is the one that fails if `syncReceipt()` was written as `$event`-dependent or the `hx-on::after-request` value was quoted wrong.

- [ ] **Step 10: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/batch_views.py core/urls.py core/templates/core/products/modals/receive_stock.html core/templates/core/products/partials/ core/test_receipt_pricing.py static/src/output.css
git commit -m "Open a delivery on as many product lines as it needs"
```

---

### Task 6: The POST — parallel arrays, all lines or none, failure keeps the work

**Files:**
- Modify: `core/batch_views.py` (`_read_receipt_lines`, `_describe_service_error`, `_posted_lines`, `_book_receipt`, `_dialog_context`)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: `ReceiptLine` (Task 2), `receive_stock` (Task 3), the row names from Task 5, `_posted_request_key` from `core/views.py:66-73`.
- Produces: the booking POST; `MAX_RECEIPT_DIALOG_ROWS` enforced at the view; `_dialog_context` gains `posted_*` keys; the failure re-render contract Task 7's migrated tests assert.

- [ ] **Step 1: Run the lane gate** on `core/batch_views.py`.

- [ ] **Step 2: Write the failing tests** — append:

```python
class ReceivePostTests(ReceiptPricingTestCase):
    def url(self):
        return reverse("core:receive-stock-question")

    def post(self, rows, *, key=None, **header):
        """rows: a list of (product_id, units, unit_cost, selling_price) tuples."""
        payload = {
            "line_product_id[]": [str(r[0]) for r in rows],
            "line_units[]": [str(r[1]) for r in rows],
            "line_unit_cost[]": [str(r[2]) for r in rows],
            "line_selling_price[]": [("" if r[3] is None else str(r[3])) for r in rows],
            "request_key": str(key or uuid.uuid4()),
        }
        payload.update(header)
        return self.client.post(self.url(), payload)

    def test_three_rows_book_one_receipt_with_three_lines(self):
        response = self.post([
            (self.product.pk, 4, "10.00", None),
            (self.bottle.pk, 6, "5.00", "9.00"),
            (self.product.pk, 1, "11.00", None),
        ], supplier_name="Noble", external_reference="INV-9", purchased_on="2026-10-31")
        self.assertContains(response, "The stock table behind this dialog already shows the change.")
        receipt = StockReceipt.objects.get()
        self.assertEqual(receipt.supplier_name, "Noble")
        self.assertEqual(receipt.purchased_on, dt.date(2026, 10, 31))
        self.assertEqual(StockBatch.objects.filter(receipt=receipt).count(), 3)
        self.product.refresh_from_db()
        self.bottle.refresh_from_db()
        self.assertEqual((self.product.stock, self.bottle.price), (5, Decimal("9.00")))

    def test_a_blank_price_is_no_change_not_a_free_product(self):
        self.post([(self.product.pk, 4, "10.00", "")])
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))
        self.assertIsNone(StockBatch.objects.get().price_applied)

    def test_the_picker_search_term_is_ignored_when_booking(self):
        """Each row's search box is name="q", so the post carries one; it must not
        become a line, a price or anything the service sees."""
        self.post([(self.bottle.pk, 2, "5.00", None)], q="Bot")
        self.assertEqual(StockReceipt.objects.count(), 1)
        self.assertEqual(StockBatch.objects.count(), 1)

    def test_a_row_without_a_product_is_refused_naming_its_row_number(self):
        response = self.post([
            (self.bottle.pk, 2, "5.00", None),
            ("", 3, "6.00", None),
        ])
        self.assertContains(response, "Line 2 has no product")
        self.assertContains(response, 'name="line_product_id[]"')
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_a_product_id_that_is_not_a_stock_item_is_refused_naming_its_row(self):
        """The service blames 'lines' as a whole for an unknown product, so the
        view resolves the ids itself -- one query -- and can say which row."""
        response = self.post([
            (self.product.pk, 4, "10.00", None),
            (uuid.uuid4(), 2, "5.00", None),
        ])
        self.assertContains(response, "Line 2 names a product that is no longer in the catalogue")
        self.assertEqual(StockReceipt.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_an_over_cap_price_is_refused_naming_its_row_number(self):
        response = self.post([(self.product.pk, 4, "10.00", "10000.00")])
        self.assertContains(response, "Line 1 cannot sell above")
        self.assertContains(response, str(MAX_SELLING_PRICE))
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_units_over_the_per_line_limit_are_refused_naming_the_row(self):
        response = self.post([(self.product.pk, 100001, "10.00", None)])
        self.assertContains(response, "Line 1 takes between 1 and")
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_arrays_of_different_lengths_are_refused_before_the_service_runs(self):
        response = self.client.post(self.url(), {
            "line_product_id[]": [str(self.product.pk), str(self.bottle.pk)],
            "line_units[]": ["4"],
            "line_unit_cost[]": ["10.00", "5.00"],
            "line_selling_price[]": ["", ""],
            "request_key": str(uuid.uuid4()),
        })
        self.assertContains(response, "incomplete")
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_more_than_fifty_rows_is_refused_at_the_view(self):
        rows = [(self.bottle.pk, 1, "5.00", None)] * 51
        response = self.post(rows)
        self.assertContains(response, "50")
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_a_failed_post_returns_the_dialog_with_every_line_still_filled(self):
        key = str(uuid.uuid4())
        response = self.post([
            (self.product.pk, 4, "10.00", "20.00"),
            (self.bottle.pk, 6, "5.00", "0.00"),
        ], key=key)
        html = response.content.decode()
        self.assertIn('value="10.00"', html)
        self.assertIn('value="20.00"', html)
        # the row partial prints a chosen name as text, never as an input value
        self.assertIn("Shea Repair Balm", html)
        self.assertIn("Bottle Gargle", html)
        self.assertIn('placeholder="no change"', html)
        self.assertContains(response, "Nothing was saved")
        self.assertContains(response, "Line 2: selling price")
        self.assertNotContains(response, "Reopen the stock dialog")

    def test_a_failed_post_keeps_the_request_key_and_a_corrected_resubmission_books_once(self):
        key = str(uuid.uuid4())
        self.post([(self.product.pk, 4, "10.00", "0.00")], key=key)
        response = self.client.post(
            self.url(),
            {
                "line_product_id[]": [str(self.product.pk)],
                "line_units[]": ["4"],
                "line_unit_cost[]": ["10.00"],
                "line_selling_price[]": ["20.00"],
                "request_key": key,
            },
        )
        self.assertContains(response, "already shows the change")
        self.assertEqual(StockReceipt.objects.count(), 1)
        self.assertEqual(StockBatch.objects.count(), 1)

    def test_replaying_an_identical_post_adds_stock_once(self):
        key = uuid.uuid4()
        rows = [(self.bottle.pk, 6, "5.00", "9.00")]
        self.post(rows, key=key)
        self.post(rows, key=key)
        self.bottle.refresh_from_db()
        self.assertEqual((self.bottle.stock, StockBatch.objects.count()), (9, 1))

    def test_a_drifted_product_refuses_the_whole_delivery_and_says_which(self):
        Product.objects.filter(pk=self.bottle.pk).update(stock=99)
        response = self.post([
            (self.product.pk, 4, "10.00", "20.00"),
            (self.bottle.pk, 6, "5.00", "9.00"),
        ])
        self.assertContains(response, "Bottle Gargle")
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_the_cashier_cannot_book_a_delivery(self):
        self.client.force_login(self.cashier)
        response = self.post([(self.bottle.pk, 6, "5.00", "9.00")])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StockReceipt.objects.count(), 0)

    def test_a_malformed_purchase_date_is_refused_with_the_dialog_intact(self):
        response = self.post([(self.bottle.pk, 6, "5.00", None)], purchased_on="31-10-2026")
        self.assertContains(response, "purchase date")
        self.assertContains(response, 'name="line_product_id[]"')
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceivePostTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: ERROR — `NameError: name '_book_receipt' is not defined` (Task 5's view already calls it).

- [ ] **Step 4: Import what the POST needs.** `core/batch_views.py` is GET-only today, so this task adds the service imports, `datetime`, `logging`, `UUID`, `timezone`, `StockReceiptSource` and `trigger_client_event`. Replace the module's import block with:

```python
import datetime as dt
import logging
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django_htmx.http import trigger_client_event

from core.inventory import (
    MAX_SELLING_PRICE,
    ReceiptLine,
    receive_stock,
)
from core.models import (
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptSource,
)
from core.views import _posted_request_key  # the same posted-key read the other write views use

from utils import is_admin  # same helper core/views.py uses

logger = logging.getLogger(__name__)

# the service names the offending line in its error_dict keys: lines[3].selling_price
LINE_KEY_RE = re.compile(r"^lines\[(\d+)\]\.(\w+)$")
FIELD_LABELS = {
    "product_id": "product",
    "quantity": "units",
    "unit_cost": "unit cost",
    "selling_price": "selling price",
}
```

Every line the current block already has stays — this is that list with `dt`, `logging`, `re`, `UUID`, `ValidationError`, `DatabaseError`, `timezone`, `trigger_client_event`, the two `core.inventory` names and `StockReceiptSource` added. Task 5's lone `from core.inventory import MAX_SELLING_PRICE` line is replaced by the block above. `require_POST` is deliberately absent: `receive_stock_question` answers GET *and* POST, like `restock_product` does today.

- [ ] **Step 5: Extend `_dialog_context`** so a re-rendered dialog carries its header fields:

```python
def _dialog_context(request, *, lines=None, request_key="", message="", posted=None):
    context = {
        "lines": lines if lines is not None else [_line_context()],
        "request_key": request_key,
        "message": message,
        "max_units": MAX_RECEIPT_LINE_UNITS,
        "max_rows": MAX_RECEIPT_DIALOG_ROWS,
        "price_cap": MAX_SELLING_PRICE,
        "presets": RECEIPT_UNIT_PRESETS,
    }
    if posted is not None:
        context["posted_supplier_name"] = posted.get("supplier_name", "")
        context["posted_external_reference"] = posted.get("external_reference", "")
        context["posted_purchased_on"] = posted.get("purchased_on", "")
    return context
```

- [ ] **Step 6: Add the reader, the error reporter and the poster** to `core/batch_views.py`:

```python
class _ReceiptLineProblem(Exception):
    """A dialog line the view cannot turn into a ReceiptLine, and its row number.

    Row 0 means "not one line's fault" -- an incomplete array, no lines at all,
    or too many of them.
    """

    def __init__(self, row, message):
        super().__init__(message)
        self.row = row
        self.message = message


def _read_receipt_lines(request):
    """Zip the dialog's parallel arrays into receipt lines, rows numbered from 1.

    An empty ``line_selling_price[]`` entry is 'change nothing', never a zero
    price, so it becomes None rather than Decimal('0.00'). Unequal array lengths
    are refused here: zipping them would silently drop a line off the end, which
    is the difference between the receipt the owner typed and one they did not.
    The per-line unit ceiling is the view's (100,000); the service keeps its own
    MAX_QUANTITY and MAX_RECEIPT_LINES rules, and this view adds the row number
    on top of them, which the service cannot know.

    The products are resolved in one query before any number is read, because a
    row has no meaning until it names a real product -- and because the service
    reports an unknown product as a single ``lines`` error that cannot say which
    row it came from.
    """
    product_ids = [value.strip() for value in request.POST.getlist("line_product_id[]")]
    units = [value.strip() for value in request.POST.getlist("line_units[]")]
    costs = [value.strip() for value in request.POST.getlist("line_unit_cost[]")]
    prices = [value.strip() for value in request.POST.getlist("line_selling_price[]")]
    if len({len(product_ids), len(units), len(costs), len(prices)}) > 1:
        raise _ReceiptLineProblem(
            0, "The receipt lines arrived incomplete. Close the dialog, reopen it and try again."
        )
    rows = list(zip(product_ids, units, costs, prices))
    if not rows:
        raise _ReceiptLineProblem(0, "Add at least one product to the receipt.")
    if len(rows) > MAX_RECEIPT_DIALOG_ROWS:
        raise _ReceiptLineProblem(
            0, f"This dialog books at most {MAX_RECEIPT_DIALOG_ROWS} lines per receipt."
        )

    picked = []
    for row, (product_id, _units, _costs, _prices) in enumerate(rows, start=1):
        if not product_id:
            raise _ReceiptLineProblem(
                row, f"Line {row} has no product yet. Pick one from the search box."
            )
        try:
            picked.append((row, UUID(product_id)))
        except (ValueError, TypeError):
            raise _ReceiptLineProblem(
                row, f"Line {row} names a product that is not a stock item."
            ) from None
    known = set(Product.objects.filter(pk__in=[pk for _row, pk in picked]).values_list("pk", flat=True))
    for row, pk in picked:
        if pk not in known:
            raise _ReceiptLineProblem(
                row, f"Line {row} names a product that is no longer in the catalogue."
            )

    lines = []
    for row, (product_id, raw_units, raw_cost, raw_price) in enumerate(rows, start=1):
        try:
            quantity = int(raw_units)
        except (TypeError, ValueError):
            raise _ReceiptLineProblem(
                row, f"Line {row} needs a whole number of units."
            ) from None
        if not 0 < quantity <= MAX_RECEIPT_LINE_UNITS:
            raise _ReceiptLineProblem(
                row,
                f"Line {row} takes between 1 and {MAX_RECEIPT_LINE_UNITS:,} units.",
            )
        if not raw_cost:
            raise _ReceiptLineProblem(row, f"Line {row} needs a unit cost.")
        try:
            unit_cost = Decimal(raw_cost)
        except InvalidOperation:
            raise _ReceiptLineProblem(row, f"Line {row} has an unreadable unit cost.") from None
        selling_price = None
        if raw_price:
            try:
                selling_price = Decimal(raw_price)
            except InvalidOperation:
                raise _ReceiptLineProblem(
                    row, f"Line {row} has an unreadable selling price."
                ) from None
            if selling_price > MAX_SELLING_PRICE:
                raise _ReceiptLineProblem(
                    row,
                    f"Line {row} cannot sell above GH₵ {MAX_SELLING_PRICE}; "
                    "checkout refuses a sale line bigger than that.",
                )
        lines.append(ReceiptLine(UUID(product_id), quantity, unit_cost, selling_price))
    return lines


def _describe_service_error(error):
    """(row number, message) for a ValidationError raised inside the service.

    The service already names the line in its error_dict key -- lines[3].
    selling_price -- so the dialog can highlight the row rather than guess it.
    Keys it raises on its own terms (``lines``, ``received_at``, the header
    fields) carry no row, and the first of those messages is the one shown.
    """
    if not isinstance(error, ValidationError):
        return 0, "Enter a valid cost, price and purchase date."
    error_dict = getattr(error, "error_dict", None)
    if error_dict:
        unrowed = None
        for key, messages in error_dict.items():
            message = (
                messages[0].message
                if hasattr(messages[0], "message")
                else str(messages[0])
            )
            match = LINE_KEY_RE.match(key)
            if match:
                row, field = int(match.group(1)), match.group(2)
                label = FIELD_LABELS.get(field, field.replace("_", " "))
                return row, f"Line {row}: {label} — {message}"
            unrowed = unrowed or message
        if unrowed:
            return 0, unrowed
    return 0, error.messages[0]


def _posted_lines(request, error_row=0):
    """The rows the owner typed, back into row-partial contexts.

    A product id that no longer resolves keeps its raw value in the hidden
    field and shows no name, so the owner sees exactly what is wrong rather
    than a silently emptied row.
    """
    product_ids = request.POST.getlist("line_product_id[]")
    units = request.POST.getlist("line_units[]")
    costs = request.POST.getlist("line_unit_cost[]")
    prices = request.POST.getlist("line_selling_price[]")
    parsed = []
    for raw_id in product_ids:
        try:
            parsed.append(UUID(raw_id))
        except (ValueError, TypeError):
            parsed.append(None)
    known = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=[pk for pk in parsed if pk is not None]
        )
    }
    rows = []
    for index, (raw_id, pk, raw_units, raw_cost, raw_price) in enumerate(
        zip(product_ids, parsed, units, costs, prices), start=1
    ):
        rows.append(
            _line_context(
                product_id=raw_id,
                product=known.get(pk),
                units=raw_units,
                unit_cost=raw_cost,
                selling_price=raw_price,
                error=(index == error_row),
            )
        )
    return rows or [_line_context()]


def _book_receipt(request):
    """One post is one receipt, or nothing at all (spec decision 3)."""
    try:
        lines = _read_receipt_lines(request)
    except _ReceiptLineProblem as problem:
        return _refused(request, problem.row, problem.message)

    raw_purchased_on = request.POST.get("purchased_on", "")
    try:
        purchased_on = dt.date.fromisoformat(raw_purchased_on) if raw_purchased_on else None
    except ValueError:
        return _refused(request, 0, "Enter a purchase date as YYYY-MM-DD, or leave it empty.")

    try:
        receipt = receive_stock(
            actor=request.user,
            request_key=_posted_request_key(request),
            lines=lines,
            received_at=timezone.now(),
            source=StockReceiptSource.PURCHASE,
            purchased_on=purchased_on,
            supplier_name=request.POST.get("supplier_name", ""),
            external_reference=request.POST.get("external_reference", ""),
        )
    except (ValueError, ValidationError) as error:
        row, message = _describe_service_error(error)
        return _refused(request, row, message)
    except DatabaseError:
        logger.exception("Multi-line receipt failed for user %s", request.user.pk)
        return _refused(request, 0, "The receipt could not be saved. Try again.")

    response = render(
        request,
        "core/products/response.html",
        {
            "type": "success",
            "message": f"{len(lines)} line(s) booked as receipt "
            f"#{str(receipt.pk)[:8]}: {sum(line.quantity for line in lines):,} units onto the shelf.",
        },
    )
    return trigger_client_event(response, "reload_products_table")


def _refused(request, row, message):
    """Re-render the dialog with its lines intact -- never response.html.

    The single-line dialog could afford to discard one shipment; ten rows of
    typed units and prices cannot be retyped because of one typo, and the
    posted request key has to survive so the corrected submission is still the
    same request to the ledger.
    """
    key = request.POST.get("request_key", "")
    # only a key that parses as a UUID is echoed back; anything else is dropped
    # so the dialog's own generator produces a fresh, safe one.
    try:
        key = str(UUID(key)) if key else ""
    except (ValueError, TypeError, AttributeError):
        key = ""
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(
            request,
            lines=_posted_lines(request, error_row=row),
            request_key=key,
            message=message,
            posted=request.POST,
        ),
    )
```

`UUID` came in with Step 4's import block. `receive_stock_question`'s GET branch keeps calling `_dialog_context(request, lines=lines)` with no `posted` — a fresh dialog has no posted header fields.

The key is minted in the browser, which buys replay protection but not a lock: **two tabs open on the same product hold two keys and book two receipts.** The spec accepts this as a residual of the client-side key; do not "fix" it here by de-duplicating on the product, because a second tab is just as likely to be a second shipment, and a server-minted key would be a `core/views.py` change this lane does not own.

- [ ] **Step 7: Run the tests** — same command as Step 2. Expected: all 15 PASS.

If `test_a_failed_post_keeps_the_request_key_and_a_corrected_resubmission_books_once` fails with "already used for different data", the *first* post was not actually refused (it stored a receipt): re-read the payload — a `0.00` price must fail validation before anything is created.

- [ ] **Step 8: Run the whole new file plus the neighbours**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing core.test_batch_ui core.test_inventory --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS. The old single-product dialog and its `RestockDialogTests` still work — Task 7 is what deletes them, so if one of them fails here, something in this task has reached into `core/views.py` it should not have.

- [ ] **Step 9: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/batch_views.py core/test_receipt_pricing.py
git commit -m "Book a whole delivery at once and keep the dialog when it fails"
```

---

### Task 7: Move the entry points and delete the single-product write

**Files:**
- Modify: `core/templates/core/partials/product_table_row.html:99-107`
- Modify: `core/templates/core/products/products.html:41-63`
- Modify: `core/views.py:529-608` (delete `MAX_RESTOCK_UNITS`, `RESTOCK_PRESETS`, `restock_product`)
- Modify: `core/urls.py:57-61` (delete the `restock-product` route)
- Delete: `core/templates/core/products/modals/restock_product.html`
- Modify: `core/test_batch_ui.py:233-327` (`RestockDialogTests` → `ReceiveDialogTests`)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: everything Tasks 4–6 produced.
- Produces: no `core:restock-product`; `views.MAX_RESTOCK_UNITS` and `views.RESTOCK_PRESETS` gone (their replacements are `batch_views.MAX_RECEIPT_LINE_UNITS` / `RECEIPT_UNIT_PRESETS`).

- [ ] **Step 1: Run the lane gate** on `core/views.py`. Then confirm nothing else reads the constants or the view:

Run: `grep -rn "MAX_RESTOCK_UNITS\|RESTOCK_PRESETS\|restock_product\|restock-product" --include=*.py --include=*.html . | grep -v "docs/"`
Expected before this task: the lines listed in this task's Files block only (plus `views.py:167 "restock_products"`, an unrelated index variable that must NOT be touched). If `core/tests.py` or `core/test_inventory.py` appears, **stop**: the other lane depends on the old endpoint and this task becomes a keep-the-route job — say so and re-plan the commit.

- [ ] **Step 2: Write the failing tests** — append:

```python
class EntryPointsTests(ReceiptPricingTestCase):
    def test_the_old_single_product_endpoint_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse("core:restock-product", args=[self.product.pk])

    def test_the_row_button_opens_the_dialog_prefilled_for_that_product(self):
        response = self.client.get(reverse("core:load-products"), {"l": 10, "p": 1})
        html = response.content.decode()
        self.assertIn(
            f'hx-get="{reverse("core:receive-stock-question")}'
            f'?product_id={self.product.pk}"',
            html,
        )
        self.assertNotIn("restock-product", html)

    def test_the_products_page_offers_a_blank_delivery(self):
        response = self.client.get(reverse("core:products"))
        self.assertContains(
            response, f'hx-get="{reverse("core:receive-stock-question")}"'
        )
        self.assertContains(response, "Receive Delivery")

    def test_the_old_dialog_template_is_gone(self):
        path = (
            Path(settings.BASE_DIR)
            / "core"
            / "templates"
            / "core"
            / "products"
            / "modals"
            / "restock_product.html"
        )
        self.assertFalse(path.exists(), "two restock dialogs is two answers to one question")
```

`Path` and `settings` come from two new imports at the top of the file:

```python
from pathlib import Path

from django.conf import settings
```

- [ ] **Step 3: Run them to verify they fail**

Expected: FAIL on all four (the route still reverses, the row still points at it, the old template still exists).

- [ ] **Step 4: Point the row button at the new dialog** — `core/templates/core/partials/product_table_row.html`, replace the `hx-get` line inside the Restock button (`:101`):

```html
              hx-get="{% url 'core:receive-stock-question' %}?product_id={{ product.id }}"
```

Keep `title="Restock this product"`, the `add_box` icon and the `sr-only` label — the owner's muscle memory for the row action is unchanged, it now opens a dialog with one row filled in.

- [ ] **Step 5: Add the hub button** — in `core/templates/core/products/products.html`, insert before the `Purchase Receipts` link (currently `:51`):

```html
        <button type="button"
                hx-get="{% url 'core:receive-stock-question' %}"
                hx-target="#modal_root"
                hx-swap="innerHTML"
                class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
          {% icon 'inventory_2' 'text-[18px] text-slate-500 dark:text-slate-400' %}
          <span>Receive Delivery</span>
        </button>
```

- [ ] **Step 6: Delete the old write path** — in `core/views.py` remove lines `529-608` (`MAX_RESTOCK_UNITS`, `RESTOCK_PRESETS` and `restock_product`) leaving the blank-line spacing between `add_product` and `remove_a_product_question` exactly two lines; in `core/urls.py` remove the `restock-product` `path(...)` block (`:57-61`); delete `core/templates/core/products/modals/restock_product.html`.

Then check the imports in `core/views.py` are still all used:

Run: `.venv/Scripts/python.exe -B -c "import core.views" && grep -c "ReceiptLine\|receive_stock\|_posted_request_key" core/views.py`
Expected: import succeeds; count > 0 (`add_product` at `:485` still uses `ReceiptLine`/`receive_stock`/`_posted_request_key`, so all three imports stay).

- [ ] **Step 7: Migrate `RestockDialogTests`** — replace `core/test_batch_ui.py:233-327` wholesale with:

```python
class ReceiveDialogTests(BatchUiTestCase):
    """The delivery dialog, in the shape the ledger books it in.

    Replaces RestockDialogTests: the single-product write (views.restock_product,
    core:restock-product, restock_product.html) is gone, so the six tests that
    pinned it are re-written against the multi-line POST. Their intents survive
    unchanged -- posted header fields are persisted, a replayed key books once,
    the cashier is turned away -- except the failure test, whose premise the
    multi-line dialog inverts: a refused post now returns the dialog with its
    lines intact instead of core/products/response.html.
    """

    def post_delivery(self, *, units="10", cost="20.00", key=None, **header):
        payload = {
            "line_product_id[]": [str(self.product.pk)],
            "line_units[]": [units],
            "line_unit_cost[]": [cost],
            "line_selling_price[]": [""],
            "request_key": str(key or uuid.uuid4()),
        }
        payload.update(header)
        return self.client.post(reverse("core:receive-stock-question"), payload)

    def test_dialog_exposes_cost_purchase_fields_and_request_key(self):
        response = self.client.get(reverse("core:receive-stock-question"))
        for name in ("line_product_id[]", "line_unit_cost[]", "request_key",
                     "purchased_on", "supplier_name", "external_reference"):
            self.assertContains(response, f'name="{name}"')

    def test_posted_cost_date_and_supplier_are_persisted_not_catalogue_defaults(self):
        key = str(uuid.uuid4())
        self.post_delivery(
            purchased_on="2026-10-31", supplier_name="Noble",
            external_reference="INV-7", key=key,
        )
        receipt = StockReceipt.objects.get(request_key=key)
        self.assertEqual(receipt.source, StockReceiptSource.PURCHASE)
        self.assertEqual(receipt.purchased_on, dt.date(2026, 10, 31))
        self.assertEqual(receipt.supplier_name, "Noble")
        self.assertEqual(StockBatch.objects.get(receipt=receipt).unit_cost, Decimal("20.00"))
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.cost), (10, Decimal("20.00")))

    def test_replaying_the_same_dialog_key_adds_stock_once(self):
        key = str(uuid.uuid4())
        self.post_delivery(key=key)
        self.post_delivery(key=key)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(StockBatch.objects.count(), 1)

    def test_saleperson_cannot_open_or_post_a_delivery(self):
        self.client.force_login(self.cashier)
        url = reverse("core:receive-stock-question")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.post_delivery().status_code, 302)

    def test_failure_returns_the_dialog_with_the_line_still_filled(self):
        """The old answer -- response.html -- deleted the work; ten rows cannot afford it."""
        failure = self.post_delivery(units="0")
        self.assertContains(failure, "Nothing was saved")
        self.assertContains(failure, 'name="line_product_id[]"')
        self.assertContains(failure, "Shea Repair Balm")
        self.assertContains(failure, 'value="20.00"')
        success = self.post_delivery()
        self.assertContains(
            success, "The stock table behind this dialog already shows the change."
        )

    def test_the_row_summary_uses_the_dialog_money_formatter(self):
        """Every money figure in the dialog goes through the x-data scope's money(),
        so a four-figure delivery cost keeps its thousands separator."""
        html = self.client.get(reverse("core:receive-stock-question")).content.decode()
        self.assertIn("this.money(cost)", self.attribute_values(html, "x-data")[0])
        self.assertNotIn("toLocaleString('en-US') + '.00'", html)
```

- [ ] **Step 8: Build, run, and check**

Run: `npm run build`
Run: `.venv/Scripts/python.exe -B manage.py test core.test_batch_ui core.test_receipt_pricing --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS.
Run: `.venv/Scripts/python.exe -B manage.py check 2>&1 | grep -Ev "GLib-GIO|AUMId"` → `System check identified no issues`. (`check` has no `--noinput`; only `test`, `migrate` and `makemigrations` do.)

- [ ] **Step 9: Live check, read-only** — and only if `showmigrations core` shows `0020` applied; otherwise write "live check deferred: the trail columns are not on the dev database yet" and move on (Task 9 repeats this step once the owner answers).

Start the server if it is down (`.venv/Scripts/python.exe -B manage.py runserver 8000 --nothreading --noreload` in the background — check first whether the other session already owns the port). In the browser as the owner: open Stock Ledger → **Receive Delivery**, search a product, add a second line, type a price, confirm the summary and the below-cost flag move, submit, and watch the table refresh. Then click a row's **Restock** button and confirm one prefilled line. **Do not book a delivery you have not planned to revert** — a receipt is PROTECT-linked and its stock is real. Prefer the failing path for the write test (submit with a blank row), which saves nothing.

- [ ] **Step 10: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/templates/core/partials/product_table_row.html core/templates/core/products/products.html core/views.py core/urls.py core/test_batch_ui.py static/src/output.css
git rm core/templates/core/products/modals/restock_product.html
git commit -m "Hand the register over to the delivery dialog and retire the single-product write"
```

---

### Task 8: The receipt surfaces — which lines changed a price, from what to what

**Files:**
- Modify: `core/batch_views.py:78-132` (`_receipt_totals`)
- Modify: `core/templates/core/inventory/receipts.html:94-96`
- Modify: `core/templates/core/inventory/receipt_detail.html:147-211` (header row, line cells, empty-state colspan)
- Test: `core/test_receipt_pricing.py`

**Interfaces:**
- Consumes: `StockBatch.price_before` / `price_applied` (Task 3), `BatchUiTestCase.tbody_rows`.
- Produces: `receipt.priced_line_count` on both the register list and the detail page; a detail table whose column order is Line, Product, Received, Unit cost, **Price was, Price now**, Sold, Adjusted, Remaining, Value remaining.

- [ ] **Step 1: Run the lane gate** on `core/batch_views.py` and the inventory templates.

- [ ] **Step 2: Write the failing tests** — append:

```python
class ReceiptSurfaceTests(ReceiptPricingTestCase):
    def register(self):
        return self.client.get(reverse("core:stock-receipts"))

    def book_mixed(self):
        return self.book(
            [
                ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00")),
                ReceiptLine(self.bottle.pk, 6, Decimal("5.00")),
            ]
        )

    def register_row(self, receipt_pk):
        """The annotated row the register template was handed for one receipt."""
        return next(
            row for row in self.register().context["page_obj"] if row.pk == receipt_pk
        )

    def test_the_register_marks_the_lines_that_changed_a_price(self):
        receipt = self.book_mixed()
        row = self.register_row(receipt.pk)
        self.assertEqual((row.line_count, row.priced_line_count), (2, 1))
        self.assertContains(self.register(), "1 line changed the selling price")

    def test_a_receipt_that_changed_no_price_carries_no_marker(self):
        receipt = self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])
        response = self.register()
        self.assertEqual(self.register_row(receipt.pk).priced_line_count, 0)
        self.assertNotContains(response, "changed the selling price")

    def test_the_detail_page_shows_the_price_a_line_found_and_the_one_it_left(self):
        receipt = self.book_mixed()
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        row = self.tbody_rows(response.content.decode())[0]
        self.assertEqual(row[4], "GH₵ 18.00")
        self.assertEqual(row[5], "GH₵ 20.00")
        self.assertEqual(row[6], "0")  # sold, still where the old column order had it

    def test_a_line_that_changed_no_price_reads_as_two_dashes(self):
        receipt = self.book([ReceiptLine(self.bottle.pk, 2, Decimal("5.00"))])
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        row = self.tbody_rows(response.content.decode())[0]
        self.assertEqual((row[4], row[5]), ("—", "—"))

    def test_a_price_below_the_lines_cost_is_flagged_not_hidden(self):
        receipt = self.book(
            [ReceiptLine(self.bottle.pk, 2, Decimal("5.00"), Decimal("4.00"))]
        )
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        self.assertContains(response, "below cost")
        self.assertEqual(StockBatch.objects.get(receipt=receipt).price_applied, Decimal("4.00"))

    def test_a_price_at_or_above_the_cost_is_not_flagged(self):
        receipt = self.book(
            [ReceiptLine(self.bottle.pk, 2, Decimal("5.00"), Decimal("5.00"))]
        )
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        self.assertNotContains(response, "below cost")

    def test_the_detail_header_gains_two_pinned_columns(self):
        receipt = self.book_mixed()
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        headers = re.findall(
            r"<th[^>]*>([^<]+)</th>", response.content.decode()
        )
        self.assertEqual(
            [h.strip() for h in headers],
            ["Line", "Product", "Received", "Unit cost", "Price was", "Price now",
             "Sold", "Adjusted", "Remaining", "Value remaining"],
        )

    def test_the_cutover_receipt_with_no_lines_still_renders_the_wider_empty_state(self):
        receipt = StockReceipt.objects.create(
            source=StockReceiptSource.OPENING,
            reason="Cutover with nothing to open.",
            received_at=timezone.now(),
        )
        response = self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))
        self.assertContains(response, 'colspan="10"')
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptSurfaceTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: FAIL — `priced_line_count` missing, `row[4]` still Sold, headers 8 long, `colspan="8"`.

- [ ] **Step 4: Aggregate the priced lines per receipt** — in `_receipt_totals()`, after the `line_count` entry:

```python
        "priced_line_count": Coalesce(
            Subquery(
                StockBatch.objects.filter(
                    receipt_id=OuterRef("pk"), price_applied__isnull=False
                )
                .values("receipt")
                .annotate(c=Count("pk"))
                .values("c")[:1],
                output_field=IntegerField(),
            ),
            0,
            output_field=IntegerField(),
        ),
```

Its own correlated subquery, for the reason the module docstring already gives: a second join over `batches` would multiply the other sums.

- [ ] **Step 5: The register marker** — `core/templates/core/inventory/receipts.html`, replace the Lines cell (`:94-96`):

```html
              <td class="tnum px-4 py-2 text-right align-middle">
                {{ receipt.line_count|intcomma }}
                {% if receipt.priced_line_count %}
                  <span class="ml-1.5 inline-flex items-center gap-0.5 rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-700 dark:bg-sky-950/60 dark:text-sky-400"
                        title="{{ receipt.priced_line_count }} line{{ receipt.priced_line_count|pluralize }} changed the selling price">
                    {% icon 'percent' 'text-[12px]' %}
                    <span>{{ receipt.priced_line_count }}</span>
                    <span class="sr-only">priced lines</span>
                  </span>
                {% endif %}
              </td>
```

- [ ] **Step 6: The detail columns** — in `core/templates/core/inventory/receipt_detail.html`, extend the header row (currently `:150-158`) between `Unit cost` and `Sold`:

```html
            <th scope="col" class="min-w-[110px] px-4 py-2 text-right font-semibold">Price was</th>
            <th scope="col" class="min-w-[130px] px-4 py-2 text-right font-semibold">Price now</th>
```

add the matching cells between the Unit cost `<td>` (`:177-182`) and the Sold `<td>` (`:183-185`):

```html
              <td class="px-4 py-2 text-right align-middle">
                <span class="tnum whitespace-nowrap text-slate-500 dark:text-slate-400">
                  {% if batch.price_before is not None %}
                    GH₵ {{ batch.price_before|floatformat:2|intcomma }}
                  {% else %}—{% endif %}
                </span>
              </td>
              <td class="px-4 py-2 text-right align-middle">
                {% if batch.price_applied is not None %}
                  <span class="tnum whitespace-nowrap font-semibold text-slate-900 dark:text-slate-100">GH₵ {{ batch.price_applied|floatformat:2|intcomma }}</span>
                  {% if batch.price_applied < batch.unit_cost %}
                    <span class="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-rose-700 dark:bg-rose-950/60 dark:text-rose-400">below cost</span>
                  {% endif %}
                {% else %}
                  <span class="text-slate-400 dark:text-slate-500">—</span>
                {% endif %}
              </td>
```

change the empty-state `colspan="8"` to `colspan="10"` (`:201`), and update the `{% comment %}` block at `:4-10` to say the detail now also shows what each line did to the selling price, the flag being computed at render (`price_applied < unit_cost`) and never stored.

- [ ] **Step 7: Fix the module docstring in `batch_views.py`** — `_receipt_totals()`'s docstring lists the columns it produces; add `priced_line_count` to that list, one clause, matching the existing voice.

- [ ] **Step 8: Build and run**

Run: `npm run build`
Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.ReceiptSurfaceTests core.test_batch_ui --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS. `test_detail_*` in `test_batch_ui.py` asserts on `row[-4:]`, which survives two columns inserted *before* Sold — if one of them fails, the insertion landed after Sold instead; fix the template, not the assertion.

- [ ] **Step 9: Commit**

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/batch_views.py core/templates/core/inventory/receipts.html core/templates/core/inventory/receipt_detail.html static/src/output.css
git commit -m "Show which receipt lines moved a selling price and where they landed"
```

---

### Task 9: The sweep — the whole suite, the invariant, and the price-change path

**Files:**
- Test: `core/test_receipt_pricing.py` (one checkout-level test), `core/test_batch_ui.py`
- No production change unless a test says otherwise.

**Interfaces:**
- Consumes: everything above.
- Produces: the green claim the final whole-branch review works from.

- [ ] **Step 1: The re-priced-then-sold end to end**, appended to `core/test_receipt_pricing.py`. `SaleLine`, `checkout`, `ReceiptLine` and `Product` are already imported by Task 1's header; add the two model names and `Sum` to it:

```python
from django.db.models import Sum

from core.models import SaleBatchAllocation, StockAdjustment
```

```python
class RepriceThenSellTests(ReceiptPricingTestCase):
    def test_a_delivery_that_reprices_a_product_makes_the_next_sale_pay_the_new_price(self):
        self.book(
            [
                ReceiptLine(self.product.pk, 10, Decimal("10.00"), Decimal("20.00")),
                ReceiptLine(self.bottle.pk, 5, Decimal("5.00"), Decimal("8.00")),
            ]
        )
        checkout(
            actor=self.admin,
            request_key=uuid.uuid4(),
            lines=[
                SaleLine(self.product.pk, 2, Decimal("40.00")),
                SaleLine(self.bottle.pk, 1, Decimal("8.00")),
            ],
        )
        self.product.refresh_from_db()
        self.bottle.refresh_from_db()
        self.assertEqual((self.product.stock, self.bottle.stock), (8, 7))

    def test_the_invariant_survives_a_reprice(self):
        """check_inventory's own rule: remaining == received + adjusted - sold.

        Both aggregates are hoisted into their own names -- `x + a or 0` binds as
        `(x + a) or 0`, which would pass on any truthy number and hide a real drift.
        """
        self.book(
            [ReceiptLine(self.product.pk, 10, Decimal("10.00"), Decimal("20.00"))]
        )
        for batch in StockBatch.objects.all():
            adjusted = StockAdjustment.objects.filter(batch=batch).aggregate(
                total=Sum("quantity_delta")
            )["total"] or 0
            sold = SaleBatchAllocation.objects.filter(batch=batch).aggregate(
                total=Sum("quantity")
            )["total"] or 0
            self.assertEqual(
                batch.quantity_remaining,
                batch.quantity_received + adjusted - sold,
            )

    def test_the_dialog_survives_a_product_name_full_of_quotes(self):
        """The one place a catalogue name reaches markup the browser compiles.

        The row prints the name as text, so escaping is Django's job; what this
        pins is that no directive attribute ever carried it -- a raw ``"`` there
        closes the attribute and hands the rest of the name to the parser.
        """
        awkward = Product.objects.create(
            name='O\'Neil "Reserve" Balm', sku="ONE1", stock=0,
            cost=Decimal("1.00"), price=Decimal("2.00"), profit_rate=Decimal("0.50"),
        )
        response = self.client.get(
            reverse("core:receive-stock-question"), {"product_id": awkward.pk}
        )
        html = response.content.decode()
        self.assertContains(response, "Reserve")
        for _tag, attributes in self.elements_with_attributes(html):
            for name, value in attributes.items():
                if name.startswith(self.JS_ATTRIBUTE_PREFIXES):
                    self.assertNotIn('"', value, f"{name} would close its own attribute")
        compile_js(self, html, **{"x-data": "expression"})
```

- [ ] **Step 2: Run them**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing.RepriceThenSellTests --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: all 3 PASS -- they test behaviour Tasks 3 and 6 already delivered, so this class is the sweep's guard, not new work. If `test_the_dialog_survives_a_product_name_full_of_quotes` fails on `assertContains`, read what actually rendered before editing anything: the escaping comes from Django, and the row partial's chosen-label markup is where a name lands.

Run: `.venv/Scripts/python.exe -B manage.py test core.test_receipt_pricing --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"`
Expected: PASS, the whole file.

- [ ] **Step 3: Management-command invariant, read-only against the real database:**

`check_inventory` takes no options at all (`--noinput` is rejected), and it reads the **dev** database, not the test one — so it only answers once the owner has applied `0020`. Run it if `showmigrations core` ends `[X] 0020…`:

Run: `.venv/Scripts/python.exe -B manage.py check_inventory 2>&1 | grep -Ev "GLib-GIO|AUMId" | head -20`
Expected: the command's own "all invariants hold" wording, exit 0. Before the migration is applied it raises `ProgrammingError: column core_stockbatch.price_before does not exist` — that is the pending migration, not a drift; report it as deferred and let `test_the_invariant_survives_a_reprice` (which runs on the test database) stand in for it.

- [ ] **Step 4: The full suite.**

Run: `.venv/Scripts/python.exe -B manage.py test core authapp --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"` (background it; ≈11 minutes, and make sure the second session is not running one at the same time)
Expected: one failure at most — `CashierReceiptTests.test_the_register_links_the_cashier_to_their_own_receipt`, and only if the clock is past 20:00 (see Global Constraints). Anything else is this plan's, and gets fixed before Step 5.

- [ ] **Step 5: The mechanical checks.**

```bash
cd C:/RebuildEden/django/myshop
.venv/Scripts/python.exe -B manage.py check 2>&1 | grep -Ev "GLib-GIO|AUMId"
.venv/Scripts/python.exe -B manage.py makemigrations core --check --dry-run --noinput 2>&1 | grep -Ev "GLib-GIO|AUMId"
npm run build
git status --porcelain core static/src/output.css
```
Expected: no issues; no pending migrations; build exits 0; the only dirty paths are the second session's, none of them yours.

- [ ] **Step 6: Commit whatever the sweep produced** (a test-only change is still a commit):

```bash
cd C:/RebuildEden/django/myshop && git branch --show-current
git add core/test_receipt_pricing.py core/test_batch_ui.py
git commit -m "Prove a re-priced delivery sells at the new price and the ledger still balances"
```

Skip the commit if the sweep changed nothing.

---

## After the last task

Run superpowers:requesting-code-review on the full range (`git log --oneline <base>..HEAD`), then superpowers:finishing-a-development-branch. The finishing step is the owner's decision — merge, PR or keep — and this plan does not make it for them.

Three things the owner needs in the final report, because they are not visible in the diff:

1. **The dev database has not seen this migration.** Nothing in this plan runs `migrate`. As of 2026-11-03 the dev DB is applied through `0019`, so `manage.py migrate` would apply only Task 1's `0020` and nothing else — say that in the report, hand over the reversal (`manage.py migrate core 0019`), and leave the decision to the owner. Until it is applied, every page that reads `StockBatch` — the batch dialog, the receipt register, the ledger — raises `ProgrammingError: column core_stockbatch.price_before does not exist`, so the live walkthrough in Step 9 of Task 7 cannot happen before the answer. If the backend lane lands new migrations first, re-run `showmigrations core` and report the real order.
2. **`profit_rate` goes staler for every re-priced product**, deliberately (spec decision 5). `Product.profit_rate` is written only by the CSV importer; the register's Margin column is computed from `price` and `cost` in SQL (`views.py:76-90`), so nothing the owner reads is wrong — but the stored column no longer matches reality after a price change, and that is accepted debt, not an oversight.
3. **Two tabs on the same product book two receipts**, because the dialog mints the request key and the backend only de-duplicates by key. The spec accepts this residual (its risk table: *the backend cannot supply one without a `views.py` change this lane does not own*), so it is a release-note line about double-tabbing, not a fix to attempt while executing this plan.
