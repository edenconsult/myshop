# Purchase Batch Tracking — UI Integration Plan (frontend only)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. This plan changes templates, one new read-only views module, URL wiring, and one new test file. It must not modify the batch backend.

**Goal:** Give the existing, already-working batch backend (receipts, costed batches, FIFO checkout, audited adjustments) its operator-facing UI: a restock dialog that actually records purchase cost/date/supplier, a working stock-adjustment dialog replacing the now-broken inline stepper, batch history per product, and a purchase-receipt register.

**Architecture:** All batch write services (`core/inventory.py`, `core/checkout.py`), models, and POST endpoints already exist and already accept the fields the UI must send. Work is therefore: (1) dialog templates that post the real field names with idempotent request keys, (2) small GET-only "ask" views for dialog context and two read-only pages, isolated in a new `core/batch_views.py` so the concurrent backend session's dirty files are never edited, (3) product-row wiring inside the existing HTMX/modal conventions.

**Tech Stack:** Django templates, HTMX, Alpine.js, Tailwind (`dark:` class strategy), local SVG sprite via `{% icon %}` + `npm run icons`, Django `TestCase` via the project venv. No new dependencies.

**Spec:** [docs/superpowers/plans/2026-11-01-purchase-batch-tracking.md](file:///C:/RebuildEden/django/myshop/docs/superpowers/plans/2026-11-01-purchase-batch-tracking.md) — this plan implements its Task 6 (owner receipt/history workflows) and its section-6 UI rows, split from the backend tasks, which are already done by another session.

## Global Constraints

- Branch is `feature/purchase-batch-tracking` (tip `d5d78c1`). A second live agent session owns this worktree's backend and switches branches; **re-run `git status` and `git branch --show-current` before every commit**, and recheck cited line numbers before editing.
- Do not edit these backend-owned, currently-dirty files: `core/views.py`, `core/models.py`, `core/forms.py`, `core/tasks.py`, `core/tests.py`, `core/admin.py`, `core/inventory.py`, `core/checkout.py`, `core/catalog_imports.py`, `core/migrations/*`, `core/management/commands/*`, `core/test_inventory.py`, `core/test_catalog_imports.py`. New UI code lives only in: `core/batch_views.py` (new), `core/urls.py` (clean, additive lines only), `core/test_batch_ui.py` (new), and templates under `core/templates/core/` (clean).
- The sales app was retired at `0938bbf`; there is no salesperson-facing batch surface. Every new route gets `@login_required` + `@user_passes_test(is_admin)` (pattern in `core/views.py:247-249`) — but never import from the views module; import `is_admin` from `utils`.
- The dev database takes real sales and history is delete-protected: **never create a checkout/sale during browser verification**. Dialog POSTs (restock/adjust) against a dedicated probe product only, or verify writes via the Django test client on the test database.
- Icons come only from the local sprite: after adding any new `{% icon 'name' %}` usage run `npm run icons`; after any template class change run `npm run build` (Tailwind scans `./**/templates/**/*.html`).
- Money displays use existing conventions: `{{ value }}` with `GH₵` prefix, `.tnum` class for numerals, `humanize` for counts; badges copy the pill classes of `core/partials/product_table_row.html:88`.
- Commits require the user's approval; each task's commit step is gated on that.

## Backend contracts this UI must match (verified in current tree)

- `restock_product` (`core/views.py:531-606`) POST fields: `units`, optional `unit_cost` (defaults `product.cost`), `purchased_on` (ISO date), `supplier_name`, `external_reference`, `request_key` (valid UUID; missing → server mints one, so retries aren't deduped unless the form sends a stable key — `_posted_request_key` at `core/views.py:66-73`). Errors render `core/products/response.html` (`type`/`message` context); success renders it too and triggers client event `reload_products_table`.
- `update_product_stock` (`core/views.py:247-285`) POST fields: `batch_id` (UUID of a batch of that product), `quantity_delta` (signed int, nonzero), `reason`, `request_key`. Failure re-renders `core/partials/product_table_row.html` with extra `error` context that the template currently ignores; success re-renders the same partial for `product` only.
- `receive_stock(...)` (`core/inventory.py:172`) — PURCHASE receipts update `Product.cost` to the line cost; non-PURCHASE sources require `reason` and mark `cost_is_estimated=True`. Replaying the same `request_key` + identical payload returns the existing receipt; reused key with different data or another actor raises `ValidationError`.
- Models (`core/models.py:69-197`): `StockReceipt(source, purchased_on, received_at, created_at, recorded_by, supplier_name, external_reference, notes, reason, request_key)`; `StockBatch(receipt→related `batches`, product→related `batches`, `line_number`, `quantity_received`, `quantity_remaining`, `unit_cost`, `cost_is_estimated`)`, FIFO index `receipt_fifo_idx`; `SaleBatchAllocation(order_item→`batch_allocations`, batch→related `sale_allocations`, `quantity`, `unit_cost)`; `StockAdjustment(batch→related `adjustments`, `recorded_by`, `quantity_delta`, `reason`, `created_at`)`. Sources: `PURCHASE`, `OPENING`, `IMPORT_OPENING`, `ADJUSTMENT_OPENING`.
- Route naming: `app_name = "core"`, kebab-case names, product routes nested under `products/` (`core/urls.py:8-73`).
- Dialog convention: buttons `hx-get` a "question" URL into `#modal_root` with `hx-swap="innerHTML"`; modals extend `partials/modal.html` blocks `overlay_attrs, dialog_attrs, modal_width, modal_icon, modal_title, modal_subtitle, modal_body, modal_footer_layout, modal_footer`; `products.html:91-198` provides the focus-trap/close controller honouring `[data-modal-close]`, `data-modal-overlay`, `[data-autofocus]`.
- Broken today: the row stepper (`core/partials/product_table_row.html:53-85`) posts only `stock`, which `update_product_stock` no longer reads — every stepper click returns the row with an invisible `error`. Task 2 replaces it.

## File map

| File | Change |
| --- | --- |
| `core/templates/core/products/modals/restock_product.html` | Editable acquisition cost, purchase metadata, stable request key (Task 1). |
| `core/templates/core/inventory/adjust_stock.html` | New batch-adjustment dialog (Task 2). |
| `core/templates/core/inventory/product_batches.html` | New per-product batch history dialog (Task 3). |
| `core/templates/core/inventory/receipts.html` + `receipt_detail.html` | New ADMIN-only purchase-register pages (Task 4). |
| `core/templates/core/partials/product_table_row.html` | Replace stepper with read-only count + adjust dialog trigger; render `error` as toast (Tasks 2–3). |
| `core/batch_views.py` | New GET-only view module: dialog context + receipt pages (Tasks 2–4). |
| `core/urls.py` | Additive `path()` entries only (Tasks 2–4). |
| `core/templates/core/products/products.html` | "Purchase Receipts" header link (Task 4). |
| `core/test_batch_ui.py` | All new tests (every task). |
| `static/icons/sprite.svg`, `static/src/output.css` | Regenerated by `npm run icons`, `npm run build` (never hand-edit). |

---

### Task 1 — Restock dialog records a real, idempotent purchase

**Files:**
- Modify: `core/templates/core/products/modals/restock_product.html` (x-data at :9-51; readonly cost row at :133-164)
- Test: `core/test_batch_ui.py` (create)

**Consumes:** `restock_product` view's existing POST fields; `StockReceipt`/`StockBatch` models.
**Produces:** A dialog posting `units`, `unit_cost`, `purchased_on`, `supplier_name`, `external_reference`, `request_key`; later tasks reuse its hidden-key pattern.

- [ ] **Step 1: Write the failing tests**

```python
# core/test_batch_ui.py
import datetime as dt
import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authapp.models import Account
from core.inventory import ReceiptLine, receive_stock
from core.models import Product, StockBatch, StockReceipt, StockReceiptSource


class BatchUiTestCase(TestCase):
    def setUp(self):
        self.admin = Account.objects.create_user(
            username="aba", password="pw", user_type="ADMIN"
        )
        self.cashier = Account.objects.create_user(
            username="kwame", password="pw", user_type="SALEPERSON"
        )
        self.product = Product.objects.create(
            name="Shea Repair Balm", sku="SHB01", stock=0,
            cost=Decimal("9.00"), price=Decimal("18.00"),
            profit_rate=Decimal("0.50"),
        )
        self.client.force_login(self.admin)


class RestockDialogTests(BatchUiTestCase):
    def test_dialog_exposes_cost_purchase_fields_and_request_key(self):
        response = self.client.get(
            reverse("core:restock-product", args=[self.product.pk])
        )
        self.assertContains(response, 'name="unit_cost"')
        self.assertContains(response, 'name="request_key"')
        self.assertContains(response, 'name="purchased_on"')
        self.assertContains(response, 'name="supplier_name"')
        self.assertContains(response, 'name="external_reference"')

    def test_posted_cost_date_and_supplier_are_persisted_not_catalogue_defaults(self):
        key = str(uuid.uuid4())
        self.client.post(
            reverse("core:restock-product", args=[self.product.pk]),
            {"units": "10", "unit_cost": "20.00", "purchased_on": "2026-10-31",
             "supplier_name": "Noble", "external_reference": "INV-7",
             "request_key": key},
        )
        receipt = StockReceipt.objects.get(request_key=key)
        self.assertEqual(receipt.source, StockReceiptSource.PURCHASE)
        self.assertEqual(receipt.purchased_on, dt.date(2026, 10, 31))
        self.assertEqual(receipt.supplier_name, "Noble")
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertEqual(batch.unit_cost, Decimal("20.00"))
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.cost),
                         (10, Decimal("20.00")))

    def test_replaying_the_same_dialog_key_adds_stock_once(self):
        url = reverse("core:restock-product", args=[self.product.pk])
        payload = {"units": "10", "unit_cost": "20.00",
                   "request_key": str(uuid.uuid4())}
        self.client.post(url, payload)
        self.client.post(url, payload)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(StockBatch.objects.count(), 1)

    def test_saleperson_cannot_open_or_post_restock(self):
        self.client.force_login(self.cashier)
        url = reverse("core:restock-product", args=[self.product.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(
            self.client.post(url, {"units": "5", "request_key": str(uuid.uuid4())}).status_code,
            302,
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python.exe -B manage.py test core.test_batch_ui.RestockDialogTests --noinput`
Expected: the first three tests FAIL (no `unit_cost`/`request_key` inputs in the current dialog); the fourth already passes.

- [ ] **Step 3: Rewrite the dialog's script block and form fields**

In `restock_product.html`, extend the Alpine state and swap the read-only cost for a real input. Replace lines 9-15 of x-data with:

```html
x-data="{
    shelf: {{ product.stock }},
    threshold: {{ product.low_stock_threshold }},
    catalogueCost: {{ product.cost|floatformat:2 }},
    unitCost: {{ product.cost|floatformat:2 }},
    price: {{ product.price|floatformat:2 }},
    maxUnits: {{ max_units }},
    requestKey: crypto.randomUUID(),
    units: 24,
```

Point the derived getters at the entered cost (`get batchCost() { return this.qty * this.unitCost; }`; margin unchanged). Add the named inputs, keeping the visible cost tile's styling:

```html
<input type="hidden" name="request_key" :value="requestKey">
<label class="...">
  <span>Unit cost (GH₵)</span>
  <input type="number" name="unit_cost" step="0.01" min="0"
         x-model="unitCost" data-autofocus
         class="tnum rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
  <small class="text-slate-500 dark:text-slate-400"
         x-show="unitCost !== catalogueCost">
    Saves to this batch; shelf default becomes GH₵ <span x-text="unitCost.toFixed(2)"></span>.
  </small>
</label>
```

Below it add an optional-details strip (Alpine `x-collapse` is not used elsewhere; a plain `<details>` element keeps it honest with existing markup):

```html
<details class="rounded-lg border border-slate-200 dark:border-slate-700">
  <summary class="cursor-pointer px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
    Purchase details (optional)
  </summary>
  <div class="grid gap-3 px-3 pb-3 sm:grid-cols-3">
    <label><span class="text-xs text-slate-500 dark:text-slate-400">Purchased on</span>
      <input type="date" name="purchased_on" class="..."></label>
    <label><span class="text-xs text-slate-500 dark:text-slate-400">Supplier</span>
      <input type="text" name="supplier_name" maxlength="255" class="..."></label>
    <label><span class="text-xs text-slate-500 dark:text-slate-400">Invoice/reference</span>
      <input type="text" name="external_reference" maxlength="255" class="..."></label>
  </div>
</details>
```

Reuse the row's input classes from `modals/product_form.html`. Delete the old readonly cost input. `crypto.randomUUID()` regenerates per dialog open; a second click inside the same opened dialog replays safely, which is what the view's `_posted_request_key` dedupe covers.

- [ ] **Step 4: Rebuild assets, run tests**

Run: `npm run build && .venv/Scripts/python.exe -B manage.py test core.test_batch_ui.RestockDialogTests --noinput`
Expected: 4 PASS.

- [ ] **Step 5: Commit (with user approval)** — `git add core/templates/core/products/modals/restock_product.html core/test_batch_ui.py` → message: `Send real purchase cost, date and retry key from the restock dialog`

---

### Task 2 — Replace the dead inline stepper with the batch-adjustment dialog

**Files:**
- Create: `core/batch_views.py`, `core/templates/core/inventory/adjust_stock.html`
- Modify: `core/templates/core/partials/product_table_row.html:51-100`, `core/urls.py` (products include)
- Test: `core/test_batch_ui.py`

**Consumes:** `update_product_stock` POST contract; `StockBatch.quantity_remaining`, `receipt.received_at/source`, `cost_is_estimated`.
**Produces:** GET `core:adjust-stock-question` → dialog posting `batch_id`/`quantity_delta`/`reason`/`request_key`; the row partial renders an `error` toast.

- [ ] **Step 1: Write the failing tests**

```python
class AdjustDialogTests(BatchUiTestCase):
    def seed_batches(self):
        for qty, cost in ((10, "20.00"), (5, "25.00")):
            receive_stock(
                actor=self.admin, request_key=uuid.uuid4(),
                lines=[ReceiptLine(self.product.pk, qty, Decimal(cost))],
                received_at=timezone.now(),
            )

    def test_question_dialog_lists_open_batches_fifo(self):
        self.seed_batches()
        response = self.client.get(
            reverse("core:adjust-stock-question", args=[self.product.pk])
        )
        self.assertContains(response, 'name="batch_id"')
        self.assertContains(response, 'name="quantity_delta"')
        self.assertContains(response, 'name="reason"')
        self.assertContains(response, 'name="request_key"')
        batches = list(response.context["batches"])
        self.assertEqual(
            [b.quantity_received for b in batches], [10, 5]
        )  # FIFO order, older first

    def test_short_count_adjustment_consumes_selected_batch(self):
        self.seed_batches()
        oldest = StockBatch.objects.order_by("receipt__received_at").first()
        response = self.client.post(
            reverse("core:update-product-stock", args=[self.product.pk]),
            {"batch_id": str(oldest.pk), "quantity_delta": "-2",
             "reason": "Damaged in transit", "request_key": str(uuid.uuid4())},
        )
        oldest.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(oldest.quantity_remaining, 8)
        self.assertEqual(self.product.stock, 15)
        self.assertContains(response, "Shea Repair Balm")
        self.assertNotContains(response, "could not be saved")

    def test_missing_batch_shows_visible_error_on_the_row(self):
        self.seed_batches()
        response = self.client.post(
            reverse("core:update-product-stock", args=[self.product.pk]),
            {"quantity_delta": "-1", "reason": "x", "request_key": str(uuid.uuid4())},
        )
        self.assertContains(response, "Select a batch")

    def test_saleperson_blocked_from_question_dialog(self):
        self.client.force_login(self.cashier)
        response = self.client.get(
            reverse("core:adjust-stock-question", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 302)
```

Run: `.venv/Scripts/python.exe -B manage.py test core.test_batch_ui.AdjustDialogTests --noinput` → FAIL: `NoReverseMatch` for `adjust-stock-question`, and `test_missing_batch...` fails while the toast is missing.

- [ ] **Step 2: Add the GET-only question view**

```python
# core/batch_views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from core.models import Product, StockBatch
from utils import is_admin  # same helper core/views.py uses


@login_required
@require_GET
@user_passes_test(is_admin)
def adjust_stock_question(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    batches = (
        StockBatch.objects.filter(product=product, quantity_remaining__gt=0)
        .select_related("receipt")
        .order_by("receipt__received_at", "line_number")
    )
    return render(
        request,
        "core/inventory/adjust_stock.html",
        {"product": product, "batches": batches},
    )
```

This decorator trio mirrors `core/views.py:247-249` (order matters for the 302 the tests assert: `user_passes_test` redirects unauthenticated logins and non-admins alike). Keep this module GET-only — all writes continue through the existing backend POST endpoints; every later view in this file repeats the same three decorators.

- [ ] **Step 3: Add the dialog template**

`core/templates/core/inventory/adjust_stock.html`, extending `partials/modal.html` (`modal_width` = `max-w-2xl`, `modal_icon` = `balance`):

```django
{% block modal_title %}Adjust Stock Count{% endblock %}
{% block modal_subtitle %}Correct the counted stock of {{ product.name }} against an open batch.{% endblock %}
{% block modal_body %}
<form hx-post="{% url 'core:update-product-stock' product.id %}"
      hx-target="#product_{{ product.id }}" hx-swap="outerHTML"
      x-data="{ dir: -1, units: 1,
                requestKey: crypto.randomUUID(),
                get delta() { return this.dir * this.units; } }"
      hx-on::after-request="document.querySelector('#modal_root [data-modal-close]')?.click()">
  <input type="hidden" name="request_key" :value="requestKey">
  <fieldset class="grid gap-2">
    <legend class="sr-only">Batch</legend>
    {% for batch in batches %}
      <label class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 {% if forloop.first %}border-emerald-400{% endif %}">
        <span class="flex items-center gap-3">
          <input type="radio" name="batch_id" value="{{ batch.pk }}" {% if forloop.first %}checked{% endif %}>
          <span class="tnum">{{ batch.receipt.received_at|date:"d M Y" }} ·
            GH₵ {{ batch.unit_cost }} <span class="text-slate-500 dark:text-slate-400">/ unit</span>
            {% if batch.cost_is_estimated %}<span class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">estimated</span>{% endif %}
          </span>
        </span>
        <span class="tnum font-semibold">{{ batch.quantity_remaining|intcomma }} left</span>
      </label>
    {% empty %}
      <p class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:bg-slate-900 dark:text-slate-400">
        No open batches. Restock the product first.
      </p>
    {% endfor %}
  </fieldset>
  <div class="flex items-center justify-center gap-2 py-1">
    <button type="button" @click="dir = -1" :class="dir === -1 && 'bg-rose-600 text-white'" class="rounded-lg px-3 py-1.5 text-xs font-semibold">Short</button>
    <button type="button" @click="dir = 1" :class="dir === 1 && 'bg-emerald-600 text-white'" class="rounded-lg px-3 py-1.5 text-xs font-semibold">Found</button>
  </div>
  <div class="flex items-center justify-center gap-2">
    <button type="button" @click="units = Math.max(1, units - 1)" class="...">{% icon 'remove' 'text-[16px]' %}</button>
    <input type="number" min="1" max="100000" x-model.number="units" class="tnum w-20 text-center ...">
    <button type="button" @click="units += 1" class="...">{% icon 'add' 'text-[16px]' %}</button>
  </div>
  <input type="hidden" name="quantity_delta" :value="delta">
  <label class="block">
    <span class="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Reason</span>
    <input type="text" name="reason" maxlength="500" required data-autofocus
           class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
  </label>
  <p class="text-xs text-slate-500 dark:text-slate-400">
    Shelf total: <span class="tnum">{{ product.stock|intcomma }}</span> ·
    correcting one batch keeps the ledger balanced.
  </p>
  <div class="flex items-center justify-end gap-2 pt-1">
    <button type="submit" class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Save adjustment</button>
  </div>
</form>
{% endblock %}
```

(`humanize` `{% load %}` at top for `intcomma`.) The after-request handler closes the dialog because the POST response is the row partial, not a dialog.

- [ ] **Step 4: Rewire the row**

In `core/partials/product_table_row.html`, replace the stepper block at lines 52-86 with a read-only count that opens the dialog, and render the view's `error` as a transient toast inside the stock cell:

```html
<div class="flex items-center gap-2">
  <button type="button"
          title="Adjust counted stock against a batch"
          hx-get="{% url 'core:adjust-stock-question' product.id %}"
          hx-target="#modal_root" hx-swap="innerHTML"
          class="tnum rounded-lg bg-slate-100 px-2.5 py-1 text-sm font-semibold text-slate-900 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700">
    {{ product.stock|intcomma }}
  </button>
  {% if error %}
    <div role="alert"
         x-data="" x-init="setTimeout(() => $el.remove(), 6000)"
         class="flex items-center gap-1.5 whitespace-nowrap rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-950/60 dark:text-amber-400">
      {% icon 'warning' 'text-[14px]' %} {{ error }}
    </div>
  {% endif %}
  ...existing status pills unchanged...
</div>
```

- [ ] **Step 5: Wire URLs**

Append inside the products `include([...])` list in `core/urls.py` (kebab style, following `restock-product`):

```python
path("stock/<uuid:product_id>/adjust/", batch_views.adjust_stock_question, name="adjust-stock-question"),
```

- [ ] **Step 6: Rebuild, run tests**

Run: `npm run icons && npm run build && .venv/Scripts/python.exe -B manage.py test core.test_batch_ui.AdjustDialogTests --noinput`
Expected: `balance` and `warning` resolve in the sprite (both names already appear in the current sprite's used-set; `balance` was newly added by this dialog, so icons build adds it); 4 PASS. Then run `.venv/Scripts/python.exe -B manage.py test core --noinput` and confirm no pre-existing test regressed from the row markup (some core tests assert row content; if they reference the old stepper, that is a finding to report to the backend session, not to fix by editing `core/tests.py`).
- [ ] **Step 7: Commit (approved)** — message: `Correct counted stock through a batch dialog instead of the dead stepper`

---

### Task 3 — Per-product batch history dialog

**Files:**
- Modify: `core/batch_views.py`, `core/urls.py`, `core/partials/product_table_row.html` (actions cell)
- Create: `core/templates/core/inventory/product_batches.html`
- Test: `core/test_batch_ui.py`

**Consumes:** `StockBatch` with related names `sale_allocations`, `adjustments`, `receipt`.
**Produces:** GET `core:product-batches` dialog; the reconciliation line `sum(remaining) == product.stock` becomes visible to the owner.

- [ ] **Step 1: Failing tests**

```python
class BatchesDialogTests(BatchUiTestCase):
    def test_shows_movement_columns_and_reconciliation(self):
        receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
            received_at=timezone.now(),
        )
        batch = StockBatch.objects.get(product=self.product)
        response = self.client.get(
            reverse("core:product-batches", args=[self.product.pk])
        )
        row = response.context["batches"][0]
        self.assertEqual(row.sold, 0)
        self.assertEqual(row.adjusted, 0)
        self.assertContains(response, "10")  # received
        self.assertContains(response, "GH₵ 20.00")

    def test_saleperson_blocked(self):
        self.client.force_login(self.cashier)
        self.assertEqual(
            self.client.get(reverse("core:product-batches", args=[self.product.pk])).status_code,
            302,
        )
```

Run to verify `NoReverseMatch` failure first.

- [ ] **Step 2: View + template**

Add to `core/batch_views.py` (same decorators as Task 2):

```python
from django.db.models import Coalesce, IntegerField, Sum

def product_batches(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    batches = list(
        StockBatch.objects.filter(product=product)
        .select_related("receipt")
        .annotate(
            sold=Coalesce(Sum("sale_allocations__quantity"), 0, output_field=IntegerField()),
            adjusted=Coalesce(Sum("adjustments__quantity_delta"), 0, output_field=IntegerField()),
        )
        .order_by("-receipt__received_at", "-line_number")
    )
    return render(
        request, "core/inventory/product_batches.html",
        {"product": product, "batches": batches,
         "remaining_total": sum(b.quantity_remaining for b in batches)},
    )
```

Template extends `partials/modal.html` with `modal_width` `max-w-3xl`, `modal_icon` `sell`: a table with columns Received on (with source badge from `receipt.get_source_display`), Unit cost (+ `estimated` pill when `cost_is_estimated`), Received (`quantity_received`), Sold (`sold`), Adjusted (`adjusted`), Remaining (`quantity_remaining`); footer line: `Sum of batches <tnum>{{ remaining_total|intcomma }}</tnum> · shelf count <tnum>{{ product.stock|intcomma }}</tnum>{% if remaining_total != product.stock %} — out of balance, use Adjust Stock Count from the Current stock column{% endif %}`; empty state `Restock this product to start batch tracking.` All-batch view (zero-remaining included) per backend-plan rule “keep depleted batches visible in history.” (RULING, Task 3 review: the originally planned `— out of balance, run reconciliation` was replaced — no reconciliation surface exists in the UI; the only correcting affordance is Task 2's Adjust Stock Count dialog. Do not reintroduce the old copy.)

- [ ] **Step 3: Row action + URL + rebuild**

Add a fourth icon button in the row's actions cell: `hx-get="{% url 'core:product-batches' product.id %}"` into `#modal_root`, icon `sell`, title “Batch history”. URL: `path("stock/<uuid:product_id>/batches/", batch_views.product_batches, name="product-batches")`.

Run: `npm run icons && npm run build && .venv/Scripts/python.exe -B manage.py test core.test_batch_ui.BatchesDialogTests --noinput` → PASS.
- [ ] **Step 4: Commit (approved)** — message: `Give each product a batch history dialog with reconciliation`

---

### Task 4 — Purchase receipt register (list + detail pages)

**Files:**
- Modify: `core/batch_views.py`, `core/urls.py`, `core/templates/core/products/products.html:41-58` (header buttons)
- Create: `core/templates/core/inventory/receipts.html`, `core/templates/core/inventory/receipt_detail.html`
- Test: `core/test_batch_ui.py`

**Consumes:** `StockReceipt` + `batches`; sources `PURCHASE/OPENING/IMPORT_OPENING/ADJUSTMENT_OPENING`.
**Produces:** Pages `core:stock-receipts` and `core:stock-receipt-detail`; the owner can inspect any receipt's lines and see how much of each is still on the shelf.

- [ ] **Step 1: Failing tests**

```python
class ReceiptPagesTests(BatchUiTestCase):
    def make_receipts(self):
        receive_stock(actor=self.admin, request_key=uuid.uuid4(),
                      lines=[ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
                      received_at=timezone.now(), supplier_name="Noble")
        receive_stock(actor=self.admin, request_key=uuid.uuid4(),
                      lines=[ReceiptLine(self.product.pk, 5, Decimal("25.00"))],
                      received_at=timezone.now() + dt.timedelta(hours=1))

    def test_list_is_newest_first_with_totals_and_source_badges(self):
        self.make_receipts()
        response = self.client.get(reverse("core:stock-receipts"))
        receipts = list(response.context["page_obj"].object_list)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0].batches__units, 5)   # newest first
        self.assertEqual(receipts[0].batches__value, Decimal("125.00"))
        self.assertContains(response, "PURCHASE")
        self.assertContains(response, "Noble")

    def test_detail_lists_lines_with_remaining_and_estimated_flags(self):
        self.make_receipts()
        receipt = StockReceipt.objects.order_by("received_at").first()
        response = self.client.get(
            reverse("core:stock-receipt-detail", args=[receipt.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Line 1")
        self.assertContains(response, "GH₵ 20.00")
        self.assertContains(response, str(receipt.id)[:8])

    def test_saleperson_blocked_from_both_pages(self):
        self.client.force_login(self.cashier)
        for name in ("core:stock-receipts",):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 1, Decimal("1.00"))],
            received_at=timezone.now())
        self.assertEqual(
            self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk])).status_code,
            302,
        )
```

Run to verify failure first.

- [ ] **Step 2: List view with fan-out-safe annotations**

Joining `batches` twice would multiply sums, so aggregate per receipt with correlated subqueries:

```python
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, OuterRef, Subquery, Sum

BATCH_VALUE = DecimalField(max_digits=24, decimal_places=2)

def stock_receipts(request):
    receipts = (
        StockReceipt.objects.select_related("recorded_by")
        .annotate(
            units=Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt").annotate(s=Sum("quantity_received"))
                .values("s")[:1]
            ),
            value=Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt")
                .annotate(s=Sum(
                    F("quantity_received") * F("unit_cost"),
                    output_field=BATCH_VALUE,
                ))
                .values("s")[:1]
            ),
            line_count=Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt").annotate(c=Count("pk")).values("c")[:1]
            ),
        )
        .order_by("-received_at", "-id")
    )
    page = Paginator(receipts, 25).get_page(request.GET.get("page"))
    return render(request, "core/inventory/receipts.html", {"page_obj": page})
```

Add `F`, `Count` etc. to the module's single `django.db.models` import line; `values("receipt").annotate(...)` groups per receipt so each correlated subquery returns exactly one row. Detail view: `get_object_or_404(StockReceipt, pk=receipt_id)`, batches annotated `sold`/`adjusted` exactly as Task 3, ordered `line_number`, plus the same totals.

- [ ] **Step 3: Pages**

`receipts.html` — extends the same page shell `products.html` uses (`_core_base.html` blocks), card-styled table (`min-w-[720px]` responsive wrapper, header classes copied from `table_search.html:129-157`): columns Receipt (link `{{ receipt.id|truncatechars:14 }}` → detail, monospace tnum), Received on (`received_at|date:"d M Y H:i"`), Purchased (`purchased_on|default:"—"`), Source badge (PURCHASE emerald / OPENING sky / IMPORT_OPENING violet / ADJUSTMENT_OPENING amber, same pill classes as the row partial), Supplier or `—`, Lines, Units, Cost value (`GH₵ {{ receipt.value }}`), By (`recorded_by`). Pagination controls copy the ledger table's pattern.
`receipt_detail.html` — header card: id, source badge, received/purchased dates, recorded_by, supplier, external reference, notes/reason when set; line table: Line N · product name/SKU · Received · Unit cost + estimated pill · Sold · Adjusted · Remaining · Value remaining (`quantity_remaining * unit_cost`); footer totals; back link to the list.
Both ADMIN-only; zero cost data may cross into any SALEPERSON template (none here — sales surface is retired).

- [ ] **Step 4: Entry link + URLs**

Products header gets a third button beside Import CSV (plain link, not dialog): `<a href="{% url 'core:stock-receipts' %}" class="...same border style as Import CSV button...">{% icon 'receipt_long' 'text-[18px]' %}<span>Purchase Receipts</span></a>`. URLs (top-level in the products include): `path("receipts/", batch_views.stock_receipts, name="stock-receipts")`, `path("receipts/<uuid:receipt_id>/", batch_views.stock_receipt_detail, name="stock-receipt-detail")`.

- [ ] **Step 5: Rebuild + tests**

`npm run icons && npm run build && .venv/Scripts/python.exe -B manage.py test core.test_batch_ui --noinput` → all PASS.
- [ ] **Step 6: Commit (approved)** — message: `Add the owner-facing purchase receipt register and line detail`

---

### Task 5 — Integrated verification and cleanup

**Files:** nothing new; evidence task.

**Consumes:** Tasks 1-4.
**Produces:** a green suite, a checked live walkthrough, and a written findings list for the backend session.

- [ ] **Step 1: Branch/state recheck** — `git branch --show-current` and `git status --short`; if the backend session committed or moved anything, re-verify the contract section's line refs before continuing.
- [ ] **Step 2: Full suite** — `.venv/Scripts/python.exe -B manage.py test core sales authapp --noinput`; expected: `core.test_batch_ui` green; document (do not fix) failures inside the backend's dirty `core/tests.py` that stem from markup they own.
- [ ] **Step 3: Migration state check** — `.venv/Scripts/python.exe -B manage.py check` and `manage.py makemigrations --check --dry-run` stay clean (the UI adds no models).
- [ ] **Step 4: Live walkthrough against the dev server** (`manage.py runserver 127.0.0.1:8000 --noreload`; the dev DB takes real writes — use the probe product only, no register sales): open Products → restock the probe product with cost 20 + supplier → dialog success tile shows, table refreshes, cost column updates; click the stock number → adjust Short 1 with reason → toast absent, batch dialog reflects 19→… wait, remaining moves; submit without reason → blocked client-side; open Batch history → movements reconcile with shelf count; open Purchase Receipts → both new receipts listed newest-first with badges and totals; detail shows line values. Double-click Save during a slow restock → single receipt (server dedupes the dialog key). Check narrow width (dialog overflow), dark mode, browser console for HTMX errors.
- [ ] **Step 5: Role probe with a second cookie jar** — sign in as a SALEPERSON account in a separate browser profile: `/products/` routes and the new receipt/adjust/batches URLs must 302; the register page markup contains no `unit_cost`/`batch_id` strings.
- [ ] **Step 6: Report findings** — anything observed on the backend side (e.g. an error path that swaps the wrong template, or the register still lacking a visible cost-drift message) goes to the user as a handoff list; do not fix outside the allowed file set.
- [ ] **Step 7: Commit (approved)** — final state `git status` shows only the intended UI files changed.

## Deferred / handed to the backend session (out of this plan's scope)

- **Multi-product receipt dialog** (one dialog posting several `ReceiptLine`s): the POST view must change; `receive_stock` already supports it. Flag for coordination.
- Report labels for actual-vs-estimated cost and batch-based valuation copy: report context is computed in the backend-owned `views.py`.
- Import dialog behaviour note: only add wording once the backend confirms whether existing-SKU imports leave stock untouched (its `catalog_imports.py` is still uncommitted).
- Physical lot/expiry, supplier settlement, returns — unchanged from the parent plan's Deferred Scope.

## Self-review record

- Spec coverage: parent plan Task 6 steps map to Tasks 1-4 here (receipt entry → restock dialog; list/detail/history → Tasks 3-4; adjustments → Task 2; browser verification → Task 5). Multi-line receipt form explicitly deferred with a named owner instead of a placeholder.
- Consistency check: all route names (`adjust-stock-question`, `product-batches`, `stock-receipts`, `stock-receipt-detail`) are used identically in tests, URLs, and templates; annotation alias names (`sold`, `adjusted`, `units`, `value`) match between views, templates, and tests.
