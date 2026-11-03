# Multi-line stock receipts with per-line selling-price changes — design

Date: 2026-11-03
Status: approved for planning by the owner; **not approved for implementation yet** (see "Lane collision")
Supersedes nothing. Builds on `docs/superpowers/plans/2026-11-02-batch-tracking-ui.md` (shipped at `f503bbf`).

## Problem

A delivery from one supplier covering ten products is booked as ten separate
restock dialogs, and the dialog cannot carry the selling price that goes with
the delivery. The owner wants one document per physical delivery and wants a
price entered on a line to become the store's price for that product.

## What is already true (verified in the current tree)

- **The service already takes many lines.** `receive_stock` accepts
  `lines: list[ReceiptLine]`, and `ReceiptLine` is `(product_id, quantity,
  unit_cost)` with no price field (`core/inventory.py:27-30`, `:172-186`). The
  single-product shape is entirely in the view, which builds one
  `ReceiptLine` and hardcodes `source=StockReceiptSource.PURCHASE`
  (`core/views.py:536-566`).
- **A receipt already re-prices the product's cost.** For a PURCHASE receipt
  the service writes each product's `cost` from the last line for that product
  and pushes it with `Product.objects.bulk_update(..., ["stock", "cost",
  "updated"])` (`core/inventory.py:283-308`). A selling-price change is the
  same shape of write, not a new kind of write.
- **A receipt is already atomic and already refuses a drifting product.** All
  lines land inside one `transaction.atomic()` after `select_for_update()` on
  every distinct product, and `_assert_product_stock` raises for any product
  whose batches disagree with its shelf before anything is created
  (`core/inventory.py:231-249`, `:159-169`).
- **Line and quantity ceilings exist.** `MAX_RECEIPT_LINES = 500`
  (`core/inventory.py:22`, enforced at `:133-134`) and `MAX_QUANTITY` as the
  int4 ceiling (`:21`). `MAX_RESTOCK_UNITS = 100_000` is a *view* constant
  (`core/views.py:529`), not a service rule.
- **Idempotency hashes the lines.** The receipt's `request_fingerprint` covers
  source, per-line product/quantity/cost, purchase date, supplier, reference,
  notes and reason (`core/inventory.py:205-222`), and replay is checked twice —
  before and inside the transaction (`:223-235`).
- **A price change mid-session fails closed, it does not silently re-charge.**
  Checkout recomputes `product.price * quantity` and rejects a cart whose total
  no longer matches: "The cart price changed. Refresh the register."
  (`core/checkout.py:150-156`). *This corrects an assumption in the prompt this
  spec came from, which said a parked cart would check out at the new price.*
- **A sale line is capped at `9999.99`** (`core/checkout.py:157-159`), so a
  price above that makes the product unsellable in a single line.
- **The receipt register, line detail, batch history and adjust dialog are
  shipped UI** (`core/batch_views.py`, `core/templates/core/inventory/*`), and
  the restock dialog already posts supplier, purchase date, reference and a
  client-generated retry key (`core/templates/core/products/modals/restock_product.html:102-220`).
- **Product search by name *or* SKU already exists** as `?s=` with
  `name__icontains | sku__icontains` (`core/views.py:1165-1166`).
- **`profit_rate` is legacy.** Only the CSV importer writes it
  (`core/catalog_imports.py:242-273`); the product form deliberately leaves it
  out because "price/cost drive the margin the dialog shows"
  (`core/forms.py:45`).

## Goals

1. One dialog books one delivery of many existing products.
2. A line may set that product's store-wide selling price; blank means no change.
3. One delivery is one ledger document, all lines or none.
4. The receipt shows which lines changed a price, from what, to what.
5. Retrying a submission cannot double-book it or double-apply a price.

## Non-goals

- Consignment as a concept: no consignment source, no ownership flag, no
  settlement, no returns. Recorded as supplier name only. Backlogged separately.
- Creating a product from a receipt line.
- A price-history model or a price-history screen.
- Editing a receipt after it is booked.
- Bulk import of a delivery sheet.

## Decisions

Owner's answers, recorded as requirements:

| # | Question | Decision |
|---|---|---|
| 1 | What does "consignment" mean here? | Out of scope; multi-line purchase + price change only |
| 2 | How much price trail? | The receipt line is the trail; no history model |
| 3 | A 10-line receipt with one bad line? | All lines or none |
| 4 | How is a 10-line receipt built? | One dialog, rows added one at a time |
| 5 | Can a line be a never-carried product? | No — existing products only |

Settled by this spec, with a reason, because they change the schema or the
failure mode and cannot be left open:

- **A price below the line's cost is accepted and flagged, not refused.**
  Deliberate loss-leaders and clearance stock are real; a hard block makes the
  dialog unusable for the case it exists for. The flag is computed when the
  detail row renders (`price_applied < unit_cost`) and borrows the existing
  `cost_is_estimated` pill's classes — it is not a stored column.
- **A line's price is capped at `9999.99`** because checkout refuses any sale
  line above it (`core/checkout.py:157`). Accepting a higher price would book
  stock the store then cannot sell.
- **Whole-receipt ceilings reuse the service's own**: at most 500 lines, and per
  product the summed quantity must stay under `MAX_QUANTITY` — both already
  enforced (`core/inventory.py:133-134`, `:297-299`). The view's
  `MAX_RESTOCK_UNITS = 100_000` stays as the *per-line* ceiling for dialog
  input; it is not a service rule and is not raised.
- **When one product appears on two lines with two prices, the last line wins**
  — mirroring the existing `last_cost` rule (`core/inventory.py:285`), so cost
  and price behave identically instead of diverging by surprise.
- **`profit_rate` is left stale on purpose.** It is not read by the register or
  the margin display; touching it here would mean reconciling a legacy column
  nobody owns. Recorded as accepted debt.

## Design

### Data model — two nullable columns on `StockBatch`, no new model

A receipt line *is* a batch (`StockBatch.receipt` + `line_number`), so the
price trail belongs on the batch row:

```
price_before  = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
price_applied = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
```

Both null on every existing row, which reads correctly as "this line changed no
price". One migration, additive only. `price_before` is what makes decision 5's
"from what" answerable without a history table.

### Service contract — `ReceiptLine` gains one optional field

```
@dataclass
class ReceiptLine:
    product_id: UUID
    quantity: int
    unit_cost: Decimal
    selling_price: Decimal | None = None
```

`receive_stock` changes in exactly four places, all inside the block that
already exists:

1. `_normalize_receipt_lines` validates the price when present — a Decimal, two
   places, `0 < value <= 9999.99` — and rejects a value outside that range
   naming `lines[i].selling_price`.
2. `line_data` in the fingerprint payload gains `"selling_price":
   str-or-None`. Without this, a replay carrying a *different* price would hash
   identically and be silently accepted as the same request.
3. Each created `StockBatch` carries `price_before` (the product's price when
   the line was read under the row lock) and `price_applied`.
4. The per-product write loop sets `product.price = last_price[product_id]` when
   that product had any priced line, and `"price"` joins the existing
   `bulk_update` field list (`core/inventory.py:305-308`).

Nothing else about the transaction, the locks, the drift refusal or the replay
check changes.

### POST shape

Parallel arrays read with `request.POST.getlist`, one entry per visible row:
`line_product_id[]`, `line_units[]`, `line_unit_cost[]`, `line_selling_price[]`.
Empty `line_selling_price[]` entries mean "no change" and must not be read as
zero. Rows are zipped by index; a length mismatch is a validation error, not a
silent truncation. This is deliberate over a JSON body: it is what an HTML form
sends without a serialisation step, and the existing dialogs already post flat
fields.

### Dialog

One modal, replacing the single-product restock dialog's body while keeping its
header fields (supplier, purchase date, invoice/reference) and its retry-key
IIFE. Below the header, a line table with an "Add another product" control.
Each row: a product picker, units, unit cost, optional selling price, and a
remove control. The picker is a **new ADMIN-only GET endpoint** that returns an
HTMX fragment of matching products as selectable options; it reuses the exact
`name__icontains | sku__icontains` expression the products table already uses
(`core/views.py:1165-1166`) rather than inventing a second search semantic.
`load_products` itself is not reused — it renders ledger rows, not options.
One row prefilled when the dialog is opened from a product's row, so the
current single-item top-up gesture is unchanged.

The dialog caps at **50 rows** and says so when the owner reaches the cap; the
service's 500-line ceiling stays as its own guard, so the UI limit is a
usability choice and not the correctness boundary.

### Failure must not destroy the work

This is the requirement the single-line version could afford to skip and the
multi-line version cannot. Today a restock failure renders
`core/products/response.html` into `#modal_root`, replacing the dialog and
discarding everything typed (`core/views.py:541-551`, and the copy fix shipped
in `1940266` only made the wording honest). With ten rows, that is ten rows of
work lost to one typo.

On failure the view re-renders **the dialog itself**, with the posted lines
still filled in, the offending row and field named, and the same retry key kept
so a corrected resubmission cannot double-book. `response.html` stays for the
success tile only.

### Receipt surfaces

- Register list (`receipts.html`): a line that changed a price adds a small
  "price" marker to the existing per-receipt line-count cell. Cheap, because
  `_receipt_totals()` already aggregates per receipt — one more `Count` with a
  `price_applied__isnull=False` filter.
- Line detail (`receipt_detail.html`): two new columns, "Price was" and "Price
  now", rendered as `—` when null, with the below-cost flag on the row.
- Batch history (`product_batches.html`): unchanged. It shows batch cost, not
  selling price, and adding price there would imply a per-batch selling price
  that does not exist.

## Error handling

| Failure | Outcome |
|---|---|
| A product on a line drifts (batches ≠ shelf) | Whole receipt refused, product named (`inventory.py:167-169`). Dialog re-renders with lines intact. |
| Unknown or missing product id | Whole receipt refused (`inventory.py:244-246`), row named |
| Units out of range for a line | Whole receipt refused, row and field named |
| Price malformed, ≤ 0, or > 9999.99 | Whole receipt refused, row and field named |
| More than 500 lines | Refused before any query runs |
| Array lengths disagree | Refused at the view, before the service is called |
| Same key replayed with identical payload | Returns the existing receipt, no second receipt, no second price write |
| Same key replayed with a **different** payload | Refused by the fingerprint check (`inventory.py:79-127`) — this is why the price must be in the payload |
| Two tabs open on the same product | Two keys, two receipts. Accepted residual of the client-side key (the backend cannot supply one without a `views.py` change this lane does not own). |

## Testing

Service level, against the real database:
- a 3-line receipt creates one receipt, three batches, moves three shelf counts;
- a blank price leaves `Product.price` untouched and leaves both new columns null;
- a priced line writes the product price **and** both columns, and the next
  checkout of that product charges the new price;
- a second line for the same product with a second price: last wins for both
  cost and price, in one receipt;
- the fingerprint changes when only a price changes (the replay test that
  catches decision 2 being skipped);
- one bad line among five leaves no receipt, no batch, no shelf move and no
  price change — including a bad *price* specifically;
- a drift on the third product of five refuses all five.

View level:
- parallel arrays build the right `ReceiptLine` list, empty price entries are
  not zeros;
- a failed post returns the dialog with the posted lines still present and the
  failing row named;
- the retry key survives a failed post and a corrected resubmission creates one
  receipt.

Markup level, following the discipline this repo has already paid for twice:
- the rendered dialog carries exactly one parseable `x-data`;
- every inline handler is extracted from the **rendered** HTML with
  `html.parser` and compiled with `new Function('event', …)` for htmx bindings
  and `new Function('$event', …)` for Alpine ones;
- the detail table's price columns are pinned by cell position, not by
  "substring appears somewhere".

Regression: the existing `core.test_batch_ui` (48 tests) and
`core.test_inventory` stay green; the checkout suite must still pass with a
price changed mid-session, which is the "refresh the register" path.

## Lane collision — why this is not implemented yet

Every file this design changes — `core/inventory.py`, `core/models.py`, a new
migration, `core/views.py`, `core/checkout.py`'s tests — is currently uncommitted
work held by a second live agent session in this same worktree
(7 modified + 13 untracked paths as of `f503bbf`). Two agents editing
`receive_stock` at once is how the ledger gets corrupted.

The implementation plan that follows is therefore written to be executable
**after** that work lands, either on a branch cut from a commit that contains it,
or with that session paused. Task ordering assumes nothing about their changes
except the contracts quoted from the current tree above, and each task
re-verifies its line references before editing.
