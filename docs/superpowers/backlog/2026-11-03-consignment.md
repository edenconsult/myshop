# Consignment receipts — backlogged, not designed

**Status:** backlog. No spec, no plan, no code. Written 2026-11-03 as the third
item of the menu that produced
`docs/superpowers/specs/2026-11-03-multi-line-receipt-pricing-design.md`, whose
Non-goals section already refuses this feature ("no consignment source, no
ownership flag, no settlement, no returns. Recorded as supplier name only").

**The ask:** some stock arrives already paid for, and some arrives still owned
by the supplier until it sells. Consignment is the second kind: the shop holds
it, sells it, and settles with the supplier afterwards, per unit sold. Returns
of unsold units are part of the same concept.

**What already exists to build on:**

- `StockReceipt.supplier_name` and `.external_reference` (`core/models.py:106-107`)
  — the paperwork fields a consignment note needs, already collected.
- `StockReceiptSource` (`core/models.py:86-90`) — four values, none meaning
  "held, not owned". A consignment receipt is a new value here.
- `StockBatch` — per-unit FIFO with `quantity_received` / `quantity_remaining`
  and `unit_cost`. Ownership is naturally a batch property, not a line one:
  the same product can be owned and held at once, and the two must not share a
  cost basis or a FIFO queue.
- `SaleBatchAllocation` + `core/inventory.py` allocation — the place that would
  have to know that a sold unit came from a batch it does not own.
- `StockAdjustment` — the drift tool that a "returned to supplier" movement
  should reuse rather than re-invent.

**Decisions a spec has to make, in order:**

1. Does a consignment batch enter the normal FIFO queue, or a separate one?
   Mixing them makes COGS wrong until settlement converts the cost.
2. Is ownership a boolean on `StockBatch`, or a `supplier_id`/`owned_at` pair
   that records the conversion? Settlement is a date, so it wants a field.
3. What settles: a report of unsold held units × the agreed cost, or an
   explicit "settle this receipt" action that books the conversion?
4. Returns: a `StockAdjustment` with a new reason kind, or a first-class
   movement model? Returns must not create negative batches.
5. Whether consignment shares the multi-line receipt dialog being planned, and
   what a held line shows differently (no selling-price change is defensible —
   the shop has not paid for the stock).

**Dependencies and sequencing:**

- `2026-11-03-multi-line-receipt-pricing.md` lands first. Consignment is a new
  source value plus ownership on that same dialog, not a parallel receipt flow.
- Every file this touches is in the batch-tracking backend lane
  (`core/models.py`, `core/inventory.py`, `core/migrations/*`), which a second
  live session currently holds uncommitted. Re-check the lane before starting,
  and expect one additive migration.
