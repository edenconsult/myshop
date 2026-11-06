# Purchase Batch Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Obtain approval of the proposed business rules before implementation.

**Goal:** Record products purchased together, retain each product batch's acquisition cost, and trace its receipt, sale, adjustments, and remaining stock without duplicating catalogue products.

**Architecture:** Add a purchase receipt header, product batch lines, sale allocations, and audited batch adjustments within the existing core application. Shared transactional inventory and checkout functions will maintain batch quantities and the existing Product.stock total; both registers will use the same FIFO allocation rules. Historical costs will be snapshotted rather than recalculated from current catalogue prices.

**Tech Stack:** Existing Python >=3.12, Django, PostgreSQL, Celery, Django templates, HTMX, Alpine.js, Tailwind, and WeasyPrint. No additional package dependency is proposed.

**Spec:** The enhanced planning brief in this conversation, with the proposed design and acceptance rules consolidated in sections 1–5 below. There is no separately approved design document. This plan is a proposal, not authorization to implement, deploy, or commit.

## Global Constraints

- “Consignment” means a purchase group, not supplier-owned goods or a supplier settlement arrangement.
- Preserve the existing Product, Order, and OrderItem identities and customer-sale meanings.
- ADMIN manages inventory and sees costs/profit. SALEPERSON uses their existing register and sees only their own sales, without acquisition costs, margins, or batch-cost payloads.
- No external assets, framework replacement, new dependency, or unrelated UI redesign.
- Do not overwrite or commit existing uncommitted work. The audited tree contains changes in authentication, stock views, registers, reports, receipts, settings, and tests.
- Use Decimal for money, positive integer purchase/sale quantities, database constraints, and PostgreSQL transaction tests.
- Plan steps are dependencies, not permission to deploy a partially batch-aware application.
- Commits, production migrations, and shared-system changes require separate authorization.

---

## 1. Current State and Integration Risks

References reflect the working tree inspected on 2026-11-01; recheck before editing.

| Area | Evidence | Consequence |
| --- | --- | --- |
| Product inventory | core/models.py:21–43 | Only aggregate stock and current catalogue cost/price exist. |
| Customer sales | core/models.py:69–101 | No purchase relationship, batch allocation, or acquisition-cost snapshot exists. |
| Restocking | core/views.py:445–479 | Restocking adds units but creates no receipt/history record. |
| Owner checkout | core/views.py:954–1091 | Product locking exists, but there is no batch allocation and money validation uses floats. |
| Salesperson checkout | sales/views.py:62–194 | Validation precedes the transaction, products are not locked, and exception handling can permit partial work. |
| Absolute stock edits | core/views.py:221–242,391–435; core/forms.py:44–103 | Direct saves can bypass batch accounting and overwrite concurrent quantities. |
| CSV import | core/tasks.py:20–121 | Existing-SKU updates use newly generated UUIDs; bulk writes bypass ordinary save hooks. |
| CLI import | core/management/commands/load_csv.py:14–47 | Separate stock-creation path must also become batch-aware. |
| Product deletion | core/views.py:493–510; core/tasks.py:124–157 | Single deletion cascades lines; bulk deletion explicitly removes whole orders, including unrelated lines. |
| Profit reports | core/views.py:530–581,695–811,1242–1275 | Historical cost/profit depends on mutable catalogue cost/price. |
| Stock valuation | core/views.py:862–905 | Existing value is stock multiplied by catalogue cost, not remaining batch cost. |
| Administrative bypass | core/admin.py:5–9 | Default model-admin writes bypass application services. |
| Tests | core/tests.py; sales/tests.py; authapp/tests.py | Existing Django TestCase coverage can be extended; real concurrency coverage is needed. |
| Schema baseline | core/migrations/0013_product_image.py | Next migration number is provisionally 0014; recheck at implementation time. |

The batch change must address the stock, costing, and deletion issues above because they directly invalidate its accounting. Unrelated report date/search defects, customer tender features, authentication redesign, and catalogue cleanup are not part of this work.

## 2. Recommended Business Rules — Approval Required

1. **One purchase receipt groups products bought together.** It is explicitly created, never inferred from a calendar date. Two purchases on the same day remain separate.
2. **One receipt can contain several product batches.** Each line has one product, quantity, and unit cost. The same product can appear on multiple receipts, or on separate lines at different costs.
3. **One posting represents one completed receipt of goods.** Purchase date and received-at time are distinct. Partial deliveries, purchase orders, and draft/post/void workflows are excluded from version one.
4. **FIFO uses received-at order**, with receipt ID and line number as deterministic tie-breakers. Opening stock precedes post-cutover receipts. An optional purchase date is informational; later backdated entries never rewrite past allocations.
5. **The cashier does not select batches.** This is accounting allocation, not proof of which physical package was picked. Physical lot/expiry tracking is a different feature.
6. **Confirmed receipt quantities, costs, product identities, and receipt dates are immutable.** Corrections create audited adjustments rather than rewriting history. Wrong historical acquisition costs require a separately approved correction workflow, not silent editing.
7. **Product.stock remains the fast operational total**, equal to the sum of its batches' remaining quantities. All application inventory writers must update both in one transaction.
8. **Product.cost becomes a reference/default purchase cost.** A new ordinary purchase receipt updates it to that product's last entered receipt-line cost. Opening receipts and adjustments do not. Product.price changes only through the existing explicit pricing workflow.
9. **No hidden stock overwrites.** Existing stock-edit controls become batch adjustments with a required reason. Catalogue edits no longer accept existing-product stock changes.
10. **Catalogue imports are not purchase receipts.** New products with quantity create clearly marked opening/import balances; existing-SKU catalogue updates leave stock untouched. Restocking existing products happens through the receipt workflow. Update the import UI to make this behavior explicit.
11. **Preserve sales and inventory history.** Block deletion of referenced products, receipts, batches, allocations, and orders. Unreferenced zero-stock products may still be deleted. Do not introduce archive/status features in this phase.
12. **Old history is not reconstructable.** Existing stock becomes opening batches. Existing sales get clearly labelled cost estimates frozen at cutover, never fake purchase allocations or guessed acquisition dates.

### Alternatives considered

- **Recommended: receipt + batches + sale allocations.** Supports multi-product purchases, different costs, remaining stock, and sales spanning receipts. Requires all stock writers to participate.
- **Restock history only.** Smaller change, but cannot reliably determine which batch remains or provide sale-specific acquisition costs; does not meet the goal.
- **Full inventory movement ledger and purchase-order subsystem.** More flexible for warehouses, returns, and settlement, but unnecessarily broad for this application.

## 3. Proposed Model Structure

```text
StockReceipt 1 ---- many StockBatch many ---- 1 Product
                           |
                           +---- many SaleBatchAllocation many ---- 1 OrderItem
                           |
                           +---- many StockAdjustment

Order 1 ---- many OrderItem
```

Names below are proposed additions, not currently existing models.

### StockReceipt

- UUID primary key; use the full UUID as the unique receipt reference.
- source: PURCHASE, OPENING, IMPORT_OPENING, or ADJUSTMENT_OPENING.
- optional purchased_on; received_at; created_at.
- recorded_by: protected account reference, nullable only for system-generated migration receipts.
- optional supplier_name, external_reference, and notes; no Supplier model or payment ledger.
- request_key: unique UUID for retry protection; request_fingerprint: SHA-256 of normalized submitted data.
- required reason for non-purchase intake outside the initial migration.
- Derived quantity/cost totals; do not add redundant persisted receipt totals.

### StockBatch

- UUID primary key; protected receipt and product references; positive line_number.
- quantity_received: positive integer; quantity_remaining: nonnegative integer.
- unit_cost: Decimal(10,2), nonnegative.
- cost_is_estimated: boolean; true for migration/opening balances without documented purchase costs.
- Unique constraint on (receipt, line_number); index on (product, receipt).
- Preserve the receipt-line sequence; allow multiple lines for the same product.
- Do not constrain remaining <= received: an audited positive correction to a known batch may make remaining exceed its originally recorded quantity.

### SaleBatchAllocation

- UUID primary key; protected order_item and batch references.
- quantity: positive integer; unit_cost: nonnegative Decimal snapshot.
- Unique constraint on (order_item, batch).
- One OrderItem remains one customer-facing product line, even when fulfilled from several batches.
- Allocation product must match the order item's product; enforce cross-table invariants in the shared service and tests.

### StockAdjustment

- UUID primary key; protected batch and recorded_by references.
- signed quantity_delta, required reason, created_at.
- unique request_key and normalized request_fingerprint for retries.
- Constraint: delta is nonzero. Service rejects any resulting negative batch or product quantity.
- A correction to known stock changes the selected batch, not its original receipt quantity/cost.
- Found stock with unknown provenance is a new ADJUSTMENT_OPENING receipt with estimated cost, not an invented addition to an unrelated historical purchase. Do not also count its quantity as a StockAdjustment.

### Existing models

- Product: preserve identity and catalogue fields; stock is no longer directly editable after creation.
- Order: add nullable unique checkout_request_key and checkout_fingerprint. Historical rows remain null. New checkout requires a stable request key.
- OrderItem: add cost_amount Decimal(20,2) and cost_is_estimated. Add nullable fields first, populate historical estimates, then make them required with no misleading default of zero.
- Keep paid_amount as the historical whole-line sale amount. Profit is paid_amount minus cost_amount, not current catalogue margin multiplied by quantity.
- Preserve existing monetary field limits in version one and reject overflow before saving. Any separate widening requires explicit scope approval; batch work must not silently change payment-field semantics.
- Change OrderItem.product and Order.user deletion behavior to PROTECT. Allocations protect tracked order lines; receipt/batch links protect inventory history. Disable direct order/line deletion in admin rather than allowing a cascade-based correction path.

### Accounting invariants

```text
Product.stock = sum(product batches.quantity_remaining)

For each batch:
quantity_remaining = quantity_received
                     + sum(adjustment.quantity_delta)
                     - sum(sale allocation.quantity)

For each new sale line:
sum(allocation.quantity) = OrderItem.qty_bought
OrderItem.cost_amount = sum(allocation.quantity * allocation.unit_cost)
OrderItem.paid_amount = validated catalogue sale price * quantity at checkout
profit = paid_amount - cost_amount
```

All new-sale allocations are complete or the whole sale rolls back. Any estimated batch makes the resulting line cost estimated. Legacy sales have frozen estimated cost_amount and zero allocations; they are never presented as batch-traced.

## 4. Transaction, Validation, and Retry Contract

Create a focused core/inventory.py and core/checkout.py rather than putting another independent stock implementation in each view. Do not rely on save signals; current bulk operations bypass them.

Proposed typed inputs and service interfaces:

```python
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

@dataclass(frozen=True)
class ReceiptLine:
    product_id: UUID
    quantity: int
    unit_cost: Decimal

@dataclass(frozen=True)
class SaleLine:
    product_id: UUID
    quantity: int
    total_price: Decimal
```

- receive_stock(*, actor, request_key: UUID, lines: list[ReceiptLine], received_at: datetime, purchased_on: date | None = None, source: str = "PURCHASE", supplier_name: str = "", external_reference: str = "", reason: str = "") -> StockReceipt.
- adjust_batch(*, actor, request_key: UUID, batch_id: UUID, quantity_delta: int, reason: str) -> StockAdjustment.
- checkout(*, actor, request_key: UUID, lines: list[SaleLine]) -> Order.
- reject invalid input using django.core.exceptions.ValidationError; views return the existing HTMX response pattern without leaking costs.

Every operation:

1. Normalize IDs, integer quantities, finite two-decimal money, and request data at the boundary. Reject fractional/zero/negative sale quantities, duplicate product IDs in a sale, unknown products, invalid cost/price values, overlong input, and overflow. Receiving may have multiple lines for the same product.
2. Claim the unique request key within the enclosing atomic transaction. Same actor + same normalized request returns the original result; changed input or another actor cannot reuse the key. Use a nested atomic savepoint for uniqueness races so handling IntegrityError does not poison the outer transaction.
3. Lock affected Product rows in primary-key order. Lock relevant batch rows in the same product order, then FIFO receipt order. Receiving, adjustment, and checkout must obey the same lock order.
4. Validate available quantities and current prices while locks are held. A stale cart price is rejected, not silently changed.
5. Persist the receipt/adjustment/order, line snapshots, allocations, batch remainders, and aggregate product quantities in one atomic transaction.
6. Catch transaction failures outside the atomic block. Never return a success response or enqueue dependent work before commit.

Use a database unique constraint for request keys, not only a disabled button. Each register keeps its key through failed network requests and regenerates it only after success or a genuinely changed cart. Receipt forms keep their key until the operation succeeds. Celery import retries reuse an operation UUID supplied at submission.

The shared checkout retains Order.user attribution and existing success templates/events. It does not return batch cost data to salesperson-facing code.

Receipt and adjustment services require an active ADMIN actor. Checkout accepts an active ADMIN or SALEPERSON actor and always attributes the order to that actor. The CLI import requires an explicit existing ADMIN account identifier; background imports receive the submitting actor and recheck authorization before applying writes. Only the historical migration may create actorless opening records. Receipt source and estimated-cost flags are assigned by trusted server workflows, not accepted as unrestricted form fields.

## 5. Migration and Historical Reporting Policy

- Run a read-only preflight for invalid product costs/quantities, broken order totals, orphaned history, and monetary overflow. Report existing inconsistencies; do not silently repair or reprice them.
- Create one system OPENING receipt and one opening batch per product with positive stock. Use current Product.cost as an explicitly estimated snapshot. Zero-stock products get no batch.
- Opening purchased_on remains null. received_at records the cutover, not a fabricated purchase date. Record the opening origin in notes/source, and make opening batches FIFO-first relative to new operations.
- Keep product counts and stock totals unchanged during backfill.
- Freeze each historical OrderItem.cost_amount at qty_bought * current Product.cost, marked cost_is_estimated=True. Preserve paid_amount and all Order totals. This is a migration-time estimate, not recovered historical cost.
- Future catalogue price/cost edits must not alter stored historical acquisition costs, including those estimates.
- Reports expose actual-cost and estimated-cost subtotals and clearly label any combined profit containing estimates. Do not label opening/legacy-derived profit as exact.
- Acquisition value becomes sum(remaining batch quantities * batch cost); current retail value may remain Product.stock * Product.price.
- Aggregate line costs before joining allocations so a multi-batch sale cannot multiply revenue, item counts, or order counts.
- Customer receipts remain ordinary product/quantity/sale-amount receipts. Never add supplier or acquisition-cost information to them.

## 6. File and Responsibility Map

Existing file locations were verified; new filenames below are deliberate proposals.

| File | Action and responsibility |
| --- | --- |
| core/models.py | Add receipt/batch/allocation/adjustment models and snapshot/idempotency fields; protect history. |
| core/migrations/0014_purchase_batch_schema.py | Proposed schema expansion migration; re-number if necessary. |
| core/migrations/0015_opening_stock_and_sale_costs.py | Historical-model RunPython backfill, snapshots, then required-field transition. |
| core/inventory.py | New receipt/adjustment transaction functions and ReceiptLine input. |
| core/checkout.py | New shared atomic checkout and SaleLine input. |
| core/batch_views.py | New ADMIN-only receipt list/detail/create, product-batch history, and adjustment endpoints. |
| core/forms.py | Receipt/line/adjustment forms; remove existing-product stock from catalogue edits. |
| core/views.py | Delegate restock/checkout/stock changes, protect deletes, switch report cost sources. |
| sales/views.py | Delegate checkout without changing salesperson ownership boundaries. |
| core/urls.py | Add receipt/history/adjustment routes; retain current restock route as a one-product entry point. |
| core/tasks.py | Route import stock through opening receipts; fix SKU-to-PK mapping; prevent destructive order deletion. |
| core/management/commands/load_csv.py | Apply the same catalogue/opening-stock import policy as the web import. |
| core/management/commands/check_inventory.py | New read-only reconciliation command; nonzero exit on an invariant failure. |
| core/admin.py | Make inventory quantities, snapshots, and audit records read-only; disable direct destructive history actions. |
| core/tests.py; sales/tests.py | Update existing integration fixtures/assertions and register/report/role coverage. |
| core/test_inventory.py | New isolated model/service/migration/reconciliation and PostgreSQL concurrency tests. |
| core/templates/core/products/products.html | Add purchase receipt/history navigation without redesigning the page. |
| core/templates/core/products/modals/restock_product.html | Capture quantity and acquisition cost using the receipt service. |
| core/templates/core/products/modals/product_form.html | Initial balance only on creation; remove direct stock editing on existing products. |
| core/templates/core/partials/product_table_row.html | Replace absolute stock controls with audited batch-adjustment entry points. |
| core/templates/core/products/modals/import_products.html | Explain catalogue update vs initial quantity behavior. |
| core/templates/core/inventory/receipt_form.html | New multi-product receipt form with per-line quantity/cost and request token. |
| core/templates/core/inventory/receipt_list.html | New receipt list, search/date filtering, and totals. |
| core/templates/core/inventory/receipt_detail.html | New lines, quantities received/sold/adjusted/remaining, and estimated-cost badges. |
| core/templates/core/inventory/product_batches.html | New product batch history and ADMIN-only adjustment form. |
| core/templates/core/orders/pos_register.html | Stable checkout request key; preserve current payload/event contract. |
| sales/templates/sales/orders/cart_table.html | Same retry key behavior without changing the sales shell. |
| core/templates/core/orders/report_body.html | Actual/estimated cost labels and batch-based valuation wording. |
| core/templates/core/orders/prints/all_reports.html | Matching PDF labels/totals. |

Update any additional current-cost display or CSV consumer found by the implementation audit. Keep changes confined to batch costs/valuation; do not rewrite unrelated filters, date periods, or PDF layout.

## 7. Ordered Implementation Tasks

Each task follows tests-first development and ends with reviewable evidence. These are local development boundaries; deploy only the integrated, reconciled result.

### Task 1 — Establish schema, input contracts, and invariant tests

**Files:** core/models.py, core/inventory.py, core/checkout.py, core/test_inventory.py, proposed schema migration.

**Consumes:** Existing Product, Order, OrderItem, and Account.
**Produces:** The models, fields, and input types in sections 3–4.

- [ ] Add model tests rejecting negative cost, zero received/allocation quantity, zero adjustment delta, duplicate receipt-line numbers, and duplicate request keys.
- [ ] Add deletion-protection tests and a test allowing two batches of one product on a receipt at different costs.
- [ ] Run the targeted tests and record their expected failure before adding schema.
- [ ] Implement the model constraints and input dataclasses exactly as specified; generate and inspect migrations instead of hand-editing the applied database.
- [ ] Verify migration forward/reverse schema behavior on a disposable database, then run model tests and Django checks.

Constraint pattern for the new model fields:

```python
models.CheckConstraint(
    condition=models.Q(quantity_received__gt=0),
    name="stock_batch_received_positive",
)
models.UniqueConstraint(
    fields=["receipt", "line_number"],
    name="stock_receipt_line_unique",
)
```

### Task 2 — Receive stock atomically and idempotently

**Files:** core/inventory.py, core/test_inventory.py.

**Consumes:** ReceiptLine and the Task 1 models.
**Produces:** receive_stock() with the section 4 signature and replay behavior.

- [ ] Add tests for mixed-product receipts, separate same-day purchases, duplicate-product lines at different costs, invalid quantities/costs, missing products, and an all-or-nothing failure in the second line.
- [ ] Add receipt retry tests: same key/same request adds stock once; changed contents or actor is rejected; two concurrent attempts create one receipt.
- [ ] Run failing tests, then implement the transaction and deterministic lock order from section 4.
- [ ] Assert batch and Product.stock totals, receipt-line costs, Product.cost default updates, and unchanged Product.price.
- [ ] Verify a failure after one batch insert rolls back the complete operation.

Representative assertion sequence, using a zero-stock product fixture and an ADMIN actor:

```python
key = uuid.uuid4()
lines = [ReceiptLine(product.id, 10, Decimal("20.00"))]
received_at = timezone.now()
receipt = receive_stock(
    actor=admin, request_key=key, lines=lines, received_at=received_at,
)
replayed = receive_stock(
    actor=admin, request_key=key, lines=lines, received_at=received_at,
)
product.refresh_from_db()
self.assertEqual(receipt.pk, replayed.pk)
self.assertEqual(product.stock, 10)
self.assertEqual(StockBatch.objects.filter(receipt=receipt).count(), 1)
```

### Task 3 — Share checkout and allocate FIFO

**Files:** core/checkout.py, core/views.py, sales/views.py, both register templates, core/tests.py, sales/tests.py, core/test_inventory.py.

**Consumes:** ReceiptLine-backed batches and SaleLine.
**Produces:** checkout() and complete SaleBatchAllocation records for every new sale.

- [ ] Add the 10-at-20 plus 5-at-25 acceptance test below and a test that editing Product.cost/price afterward does not alter its stored acquisition cost/profit.
- [ ] Add invalid-cart tests for duplicate product IDs, fractional/negative/zero quantities, non-finite money, stale price, field overflow, and insufficient combined stock.
- [ ] Add both-role integration tests preserving actor ownership, HTMX events, receipt rendering, and cost-field exclusion from salesperson responses.
- [ ] Run failures, implement shared checkout, and replace both view implementations with thin adapters.
- [ ] Add stable request keys to both registers; verify timeout/retry does not sell twice and a changed cart cannot reuse a successful key.
- [ ] Run TransactionTestCase tests using separate PostgreSQL connections for overlapping sales, concurrent receipt/sale, opposite cart ordering, rollback after allocation failure, and duplicate submission.

FIFO acceptance test body with valid product/admin fixtures:

```python
product.price = Decimal("40.00")
product.save(update_fields=["price"])
received_at = timezone.now()
receive_stock(
    actor=admin, request_key=uuid.uuid4(),
    lines=[ReceiptLine(product.id, 10, Decimal("20.00"))],
    received_at=received_at,
)
receive_stock(
    actor=admin, request_key=uuid.uuid4(),
    lines=[ReceiptLine(product.id, 5, Decimal("25.00"))],
    received_at=received_at + datetime.timedelta(seconds=1),
)
order = checkout(
    actor=admin, request_key=uuid.uuid4(),
    lines=[SaleLine(product.id, 12, Decimal("480.00"))],
)
line = OrderItem.objects.get(order=order)
product.refresh_from_db()
self.assertEqual(product.stock, 3)
self.assertEqual(line.cost_amount, Decimal("250.00"))
self.assertEqual(line.paid_amount - line.cost_amount, Decimal("230.00"))
self.assertEqual(
    sorted(SaleBatchAllocation.objects.filter(order_item=line)
           .values_list("quantity", "unit_cost")),
    [(2, Decimal("25.00")), (10, Decimal("20.00"))],
)
```

The cost snapshot is calculated using Decimal arithmetic:

```python
cost_amount = sum(
    (allocation.quantity * allocation.unit_cost for allocation in allocations),
    Decimal("0.00"),
)
```

Keep one OrderItem per sale product; splitting it by batch would change receipt line counts and existing report semantics.

### Task 4 — Close stock-write and deletion bypasses

**Files:** core/inventory.py, core/forms.py, core/views.py, core/tasks.py, core/management/commands/load_csv.py, core/admin.py, product editing/import templates, core/tests.py, core/test_inventory.py.

**Consumes:** receive_stock(), batch models, and protected history.
**Produces:** adjust_batch(); all supported stock mutations satisfy the accounting invariants.

- [ ] Add tests for signed corrections, missing reasons, correction below zero, unknown-provenance opening intake, and adjustment retries.
- [ ] Add tests proving catalogue edits cannot overwrite stock after a simultaneous checkout.
- [ ] Add real importer tests, not just task-dispatch mocks: new SKU with opening stock, existing-SKU metadata update preserving stock, correct existing PK association, malformed rows, duplicate/conflicting names/SKUs, and a retry after failure.
- [ ] Implement adjust_batch() with the same transaction/lock order as checkout. Replace absolute stock updates with selected-batch corrections and explicit reasons.
- [ ] On product creation, create the catalogue product at zero stock and its initial balance in one transaction; failure must not leave a stocked product without batches.
- [ ] Update web and CLI catalogue import behavior. Existing-product QUANTITY is not applied; surface this explicitly. Use actual persisted identities and accurate success/failure counts.
- [ ] For async imports, propagate the actor and stable operation UUID from HTTP submission. Pre-validate input; apply catalogue changes and opening receipts in one all-or-nothing transaction, with batched SQL where needed. Do not silently skip conflicting rows or post half an import.
- [ ] Remove explicit order deletion from the bulk product task. Pre-check protected references, report blocked products, and never loop endlessly over protected rows. Treat an empty ID list as no operation/error, not all products.
- [ ] Restrict model admin inventory/cost-snapshot mutation and history deletion. Disable admin creation of products and transactional records where it would bypass the services; keep permitted product metadata edits field-limited. Verify that only never-referenced zero-stock products can be deleted.

An absolute catalogue save must not include stock:

```python
Product.objects.filter(pk=product.pk).update(
    name=cleaned_data["name"],
    cost=cleaned_data["cost"],
    price=cleaned_data["price"],
)
```

This snippet illustrates field-limited persistence; preserve the form's other current editable metadata fields explicitly rather than replacing them with a partial implementation.

### Task 5 — Backfill opening balances and frozen legacy estimates

**Files:** proposed backfill migration, core/management/commands/check_inventory.py, core/test_inventory.py.

**Consumes:** Task 1 schema; legacy Product/OrderItem values.
**Produces:** Reconciled opening batches, complete cost snapshots, and a read-only audit command.

- [ ] Use MigrationExecutor tests to move a disposable database from the prior schema, seed positive/zero stock and historical sales, and run the backfill.
- [ ] Assert no changed Product.stock, order IDs, paid_amount, or order totals; all historical sale costs are estimated; no historical allocation is invented.
- [ ] Implement RunPython with apps.get_model() historical models and the migration database alias, not imports from current services.
- [ ] Batch inserts/updates to bound memory. Use one migration transaction and a reserved opening-receipt source; retry a failed migration only after confirming its recorded state.
- [ ] Add required-field transitions only after snapshot population succeeds. Update existing legacy-sale fixture helpers to explicitly set estimated cost snapshots; new-sale integration fixtures must receive stock and use checkout rather than directly creating incomplete order lines.
- [ ] Implement check_inventory to verify product totals, batch conservation, complete new-sale allocation sums, snapshot sums, and matching products on allocations. Identify new sales through their non-null checkout_request_key so accidentally missing allocations cannot masquerade as legacy history. Raise CommandError on mismatches; never auto-repair.
- [ ] Test reconciliation against intentionally broken aggregates and cross-product allocations.
- [ ] Mark data reversal as unsafe/irreversible once tracked transactions exist; do not ship a rollback that deletes financial history.

Expected frozen historical estimate:

```python
estimated_cost = historical_item.qty_bought * historical_product.cost
self.assertEqual(migrated_item.cost_amount, estimated_cost)
self.assertTrue(migrated_item.cost_is_estimated)
self.assertFalse(
    SaleBatchAllocation.objects.filter(order_item_id=migrated_item.pk).exists()
)
```

### Task 6 — Add owner receipt and batch-history workflows

**Files:** core/batch_views.py, core/forms.py, core/urls.py, proposed inventory templates, existing product/restock templates, core/tests.py.

**Consumes:** receive_stock(), adjust_batch(), receipt/batch read models.
**Produces:** ADMIN-only receipt entry/history and product-batch inspection using existing styling/HTMX patterns.

- [ ] Add route tests for anonymous access, salesperson denial, POST-only mutations, form errors, duplicate submission, and single/multi-product receipt success.
- [ ] Implement a receipt form with purchase date, received-at, optional supplier/reference, and product/quantity/unit-cost lines. Show totals before posting.
- [ ] Adapt the existing Restock action into a one-product receipt shortcut with editable acquisition cost; do not silently substitute catalogue cost for a submitted batch cost.
- [ ] Show receipt quantities received, sold, adjusted, and remaining; purchase cost; remaining acquisition value; and estimated-cost markers. Keep zero-balance batches visible in history.
- [ ] Make adjustments require an identified batch and reason; unknown stock uses the clearly labelled opening-adjustment action.
- [ ] Start the development server against disposable/local test data and use a browser to receive multiple products, receive the same product again, sell across batches from both registers, inspect history, and submit a correction.
- [ ] Check invalid forms, duplicate submits, narrow layouts, existing product search/modals, browser console, and network failures. Do not claim UI verification from template tests alone.

### Task 7 — Switch reporting to stored acquisition costs

**Files:** core/views.py, core/templates/core/orders/report_body.html, core/templates/core/orders/prints/all_reports.html, core/tests.py; any verified CSV consumers of the same report context.

**Consumes:** OrderItem.cost_amount/cost_is_estimated and batch remainders.
**Produces:** Stable historical costs/profit and current batch-valued inventory with explicit estimate labels.

- [ ] Add tests for a multi-batch order, a mixed actual/estimated-cost order, all-legacy periods, empty periods, and repricing after sale.
- [ ] Replace cost/current-margin calculations across dashboard, ledger, receipt-report rows, CSV, and PDF with stored cost snapshots and actual paid revenue.
- [ ] Expose estimated-cost line/order counts and actual/estimated cost/profit subtotals. A combined figure with any estimate must be labelled estimated or partly estimated.
- [ ] Calculate acquisition stock value from remaining batch quantities. Retain current-price retail value separately.
- [ ] Assert receipt/line/order counts and revenue are not multiplied by allocation joins.
- [ ] Verify HTML, CSV, and rendered PDF agree for the same date range and sale population; preserve salesperson receipt ownership and cost confidentiality.

Report arithmetic for each historical sale line:

```python
profit = line.paid_amount - line.cost_amount
is_estimated = line.cost_is_estimated
```

Do not recompute either line revenue or line cost from current product prices. Existing unrelated discrepancies between order-header totals and surviving lines must remain visible as preflight findings, not be concealed by the migration.

### Task 8 — Verify integrated behavior and rehearse cutover

**Files:** Tests and implementation files above; no deployment/CI configuration changes are pre-authorized.

**Consumes:** Tasks 1–7.
**Produces:** Test evidence, reconciliation evidence, and a reviewed deployment decision.

- [ ] Run the commands below using an isolated PostgreSQL test database; SQLite cannot validate the locking and PostgreSQL indexes used here.
- [ ] Confirm both registers, imports, stock corrections, product creation, and administration cannot produce stock without batch accounting.
- [ ] Rehearse migrations and reconciliation on a recent authorized backup in an isolated environment. Record elapsed time and memory use for large inventories/imports.
- [ ] Complete the browser scenario from Task 6 and compare actual/estimated reports and PDFs after catalogue repricing.
- [ ] Obtain approval and a verified backup before production changes. Pause web inventory/sale writes, Celery imports/deletions, and manual import commands; drain old workers before backfill.
- [ ] Deploy all batch-aware writers together, run migrations and read-only reconciliation, then smoke-test before reopening writes. Do not mix old workers with the new schema/write rules.
- [ ] If rehearsal or pre-open checks fail, keep writes closed and investigate. After new transactions exist, do not restore an old backup or drop batches without a separately approved recovery procedure that preserves those transactions.

Commands for implementation-time verification, not executed during planning:

```bash
.venv/Scripts/python.exe -B manage.py check
.venv/Scripts/python.exe -B manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -B manage.py test core.test_inventory --noinput
.venv/Scripts/python.exe -B manage.py test core sales authapp --noinput
.venv/Scripts/python.exe -B manage.py check_inventory
.venv/Scripts/python.exe -B manage.py runserver 127.0.0.1:8000 --noreload
```

The last two commands require the proposed implementation and an appropriately prepared local database. The normal settings load .env and configure PostgreSQL; verify the target explicitly before any migration or data-writing browser exercise.

## 8. Release Acceptance Checklist

- [ ] One receipt groups multiple products, with independent line costs and quantities.
- [ ] Two purchases of the same product on the same date remain distinct.
- [ ] Receiving 10 units at 20 and 5 units at 25, then selling 12, leaves 3 units, records cost 250, and retains one customer sale line.
- [ ] A partially consumed batch remains visible; a depleted batch retains history.
- [ ] Changing catalogue cost/price does not change saved acquisition costs/profit.
- [ ] Opening/legacy costs remain explicitly estimated, never falsely described as actual historical purchase costs.
- [ ] No purchase, checkout, adjustment, or import retry creates duplicate inventory/sales.
- [ ] Concurrent operations cannot oversell, lose a receipt, or diverge batch/product totals.
- [ ] A failed line rolls back the full transaction.
- [ ] All current stock-entry paths use the batch-aware rules; existing-SKU catalogue import never overwrites quantity.
- [ ] Historical products/orders cannot be erased through the current bulk-delete path or admin bypass.
- [ ] SALEPERSON sees neither acquisition costs nor another person's sales.
- [ ] Dashboard/report/CSV/PDF totals agree without multi-allocation join inflation.
- [ ] Read-only reconciliation passes before reopening production writes.

## 9. Deferred Scope

Supplier ownership/payments, supplier entities, purchase orders, partial deliveries, physical lot/expiry/serial tracking, multi-warehouse stock, landed-cost allocation, manual sale-batch selection, refunds/returns/voids, posted purchase-cost amendments, and product archiving are excluded. Existing sales deletion is blocked, not rebranded as a refund. If returns/voids are later approved, they need explicit reversal allocations and financial rules rather than direct stock increments.

## 10. Design Checkpoint

The principal behavior changes to approve are automatic FIFO, explicit purchase grouping, audited stock corrections instead of quantity overwrites, catalogue imports preserving existing quantities, frozen but labelled legacy cost estimates, and protected history instead of destructive deletion.

No implementation, test run, migration, deployment, or commit has been performed as part of preparing this plan.
