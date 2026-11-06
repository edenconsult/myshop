# 07 — Remove products

## What this is for

Taking a line off the shelf list for good: a product you will never stock again, or a batch
of test lines that got typed in and need clearing out. This is not "hide it for now" — the
shop has no hide. When a product goes, its code, its prices and its count go with it.

## You need

- **Role.** The owner's account, for both routes. A cashier cannot see the bin icon, cannot
  reach either address, and gets the sign-in page instead of a refusal; if a line must go, it
  waits for the owner.
- **Screen.** Two dialogs over the **Products & Inventory** ledger: **Remove This Product** for
  one line, opened by a row's bin icon, and **Remove N Products** for several, opened by
  **Remove selected** in the bar that appears above the table once rows are ticked.
- **How to get there.** Sign in as the owner, open **Products & Stock**, find the product — the
  search box takes a name or a code, and the `/` key jumps the caret into it — then press the
  bin at the right of its row. For several at once, tick their checkboxes first.
- **Data that must already exist.** For the bulk route, at least one ticked row (ticks carry
  across pages until you confirm or reload) and the background worker running, because bulk
  deletion is handed to it. For either route, realistically, a product at zero with no sales
  and no stock movement of any kind behind it — see "When it goes wrong". Almost everything
  actually stocked fails that test, and the shop says so instead of deleting.

## Steps

### 1. Open the removal question on one product

Press the bin at the right of the row. Nothing has been deleted yet; this dialog is a
question.

![The Remove This Product dialog over the ledger: the product card for Active Men Cream reading NO CODE • SKINCARE, a rose panel headed THIS ACTION CANNOT BE UNDONE listing 5 shelf units written off and 1 order line deleted with it, and the two footer buttons Keep Product and Remove From Ledger.](img/07-removal/07-remove-one-dialog.png)

### 2. Read what the dialog says it will cost you

- The heading is "Remove This Product" and the line under it is "Deleting is irreversible —
  the SKU and its shelf count go with it."
- The grey card repeats the item so you know which one you are about to lose: its tile
  initials, its name, then its code or "No code", a dot, and its category — here
  "NO CODE • SKINCARE".
- The rose panel, "THIS ACTION CANNOT BE UNDONE", carries two lines built from that product's
  own numbers: "5 shelf units are written off." and, for an item that has sold,
  "1 order line — every past register sale of this item — is deleted with it, and drops out of
  the sales reports." An item that has never sold reads "No order lines reference this
  product, so past sales are untouched." instead. The first line never bends for a single
  unit, so one unit reads "1 shelf units are written off."
- The footer offers **Keep Product** on the left and **Remove From Ledger** on the right, in
  red, and the red one takes the keyboard focus when the dialog opens. Press **Keep Product**
  whenever you are not certain.

### 3. Press the red button

**The step ends at the button.** What happens after it is described in words, because the
captures for this chapter were taken without writing to the shop's data and no deletion was
ever completed in front of a camera: either a card headed "Ledger updated" saying
"`<name>` was removed from the ledger.", or a card headed "Nothing was saved" saying only
"`<name>` has inventory or history and cannot be deleted." — which is the shop refusing
without telling you which of its three reasons it found. Both carry one **Back to ledger**
button. On the success the table behind it has already redrawn without that row; on the
refusal nothing moves, because nothing changed.

### 4. For several products, tick and press "Remove selected"

Tick the rows' checkboxes on the ledger. A bar appears above the table reading
"N selected", with **Remove selected** at its right. **This step and the two that follow have
no screenshots** — the bulk path was never run for these captures — so the frames are
described. Pressing the button posts your ticked list and returns a confirmation dialog headed
"Remove 18 Products" (the count is the number of rows you ticked) with the line "Bulk deletion
runs on the worker and cannot be undone."

### 5. Read the bulk confirmation

- A list of the names being removed, alphabetically, **six at most**; anything past the sixth
  is folded into a final grey line, "and 12 more selected rows". The list is a sample, so do
  not treat the six names as the whole deal.
- The same rose panel, "This action cannot be undone", with three lines:
  "N shelf units written off across the selection.", then either "N order lines referencing
  these products is deleted too, and drops out of the sales reports." or "No order lines
  reference these products, so past sales are untouched.", and finally "Orders that only
  contained other items stay in the register history."
- The footer: **Keep Products** and a red **Remove 18 Products**, which reads "Removing…"
  while the request is in flight.

### 6. Confirm, and watch — or don't

**The step ends at the red button.** Afterwards, in words: the list goes to the worker and the
dialog becomes a progress dialog headed "Removing Products", with a bar, the task's first
eight characters under the title, and a running line under the bar of the shape
"N out of M selected products removed". While it is moving the footer button reads
**Stop watching**, and the small print says "Closing this dialog does not stop the deletion —
the worker keeps running and the table refreshes when it is done." The first half of that is
true and the second half is not: the refresh rides on the same polling that paints the bar, so
closing the dialog cancels it too. When the worker reports back the heading becomes "Removal
Complete" and the body line reads "The worker finished. The ledger behind this dialog no
longer lists the removed products.", with **Back to ledger** to close it. That fixed sentence
is all a finished bulk run ever says, and it says nothing about the lines it refused. The
worker does work out what went and what it held back and writes both into a closing line —
"Done: removed 4; 2 products were protected by stock or history." is its shape — but nothing
on this screen prints it: a run that ends without an error gets the fixed sentence above, and
the breakdown is dropped with the return value.

## When it goes wrong

- **"Active Men Cream has inventory or history and cannot be deleted."** under a heading of
  **"Nothing was saved"**. This is the refusal, and it is the normal outcome for anything on
  the shelf: the shop will not delete a product whose count is not zero, that appears on any
  past sale, or that has ever had a batch written against it — by a delivery, by an import row
  carrying a quantity, or by the opening units typed into the Add New Product dialog. Any one
  of those three is enough to hold the line in place, and the card never says which one it
  found.
- **"Reopen the stock dialog for this product and enter the details again."** — the second
  line of that same refusal card. It is the shop's generic failure text, and it is wrong here:
  nothing you re-enter will make this product deletable. The fix is not to remove it; see the
  notes below.
- **"No products were selected, so nothing was queued. Tick the rows to remove and try
  again."** — the bulk confirmation was asked for with an empty list, so nothing was handed to
  the worker at all.
- **"Removing Products" with the bar at 0% and "Waiting for the worker…" under it**, changing
  nothing. That is the worker being down rather than a slow job; the request is sitting in the
  queue and will run when a worker picks it up. **Stop watching** closes the dialog without
  cancelling the queued job — it only gives up the watching, and the ledger refresh that comes
  with it.
- **"Removal Failed"** as the heading, with the worker's own sentence in the red band under the
  bar. Read that band: it is the only place the failure is written down.
- **Rows that vanish from the count without vanishing from the ledger.** In a bulk run,
  protected products are skipped quietly, and the skipping leaves no record at all. While the
  job is moving, the gap in the progress line is the only sign of it: "4 out of 6 selected
  products removed" says two are being held back. When the job ends, that line is replaced by
  "All rows processed" and both numbers go with it. Nothing lists the held-back rows, nothing
  is written down about them, and the closing card never mentions them. So the way to know
  what a bulk removal refused is to look afterwards at the products you cared about: reload
  the ledger and see which of them are still on it.
- **The button that never appears.** There is no "Deactivate", "Archive", "Hide" or
  "Make inactive" control anywhere on the product row, in the edit dialog, or in the bulk
  confirmation. Removal is deletion, and the bin icon is the only exit.

## Notes & limits

- **The warnings on the question dialogs describe a deletion the shop will not carry out.**
  The one-product dialog promises to write off "5 shelf units" and delete "1 order line", yet
  a product with units or sales is refused the moment you press the button. What this screen
  can actually delete is a product at zero, that has never appeared on a sale, *and* that has
  never had a batch written against it. Only the first two of those show on the rose panel, so
  a panel reading "0 shelf units are written off." and "No order lines reference this product,
  so past sales are untouched." is a necessary sign and not a guarantee — a sold-out line that
  once received stock still has its batch and is still refused. The same is true in bulk: the
  confirmation totals units and order lines that the worker then refuses to touch, and it says
  nothing about which of them it spared.
- **A product that has ever had a stock movement is effectively permanent**, even after it
  sells down to zero, because the batch record protects it. A delivery writes one, an import
  row with a quantity writes one, and so do the opening units typed into the Add New Product
  dialog. That is the shop protecting its audit trail, not a bug you have to work around.
- **So a discontinued line is normally left in place at zero**, and simply stops appearing on
  the register: the till lists only items with stock. The ledger keeps it, the depleted tile
  counts it, and reports stay honest.
- **Nothing here is a partial removal.** You cannot delete a product's photo, code or price
  history on their own, and you cannot remove stock without a delivery or a counted correction
  (chapters 05 and 06).
- **Bulk runs on the worker, one product at a time in chunks.** The ledger redraws itself when
  the job ends only if the dialog is still open to hear it: the refresh arrives on the same
  poll that paints the bar, so closing the dialog — **Stop watching**, the cross, or Escape —
  cancels the refresh along with the watching. The counts you are left looking at are the ones
  from before the run, and reloading the page is what shows you the truth. The deletion itself
  carries on either way.
- **The single-product path does not use the worker** — it answers immediately, which is why
  one refusal is instant and a bulk run has a progress bar.
- **The bulk confirmation's six-name list is a preview of the request, not a preview of the
  result.**
- **What only the other role sees:** none of it. A cashier cannot delete, cannot see the bin
  icon, and cannot reach either address; if a line must go, it waits for the owner.

Related chapters: 04 for the ledger and its row icons, 05 for receiving stock back onto a line
you kept, 06 for correcting a count to zero, 13 for the worker and the gaps this screen leaves.
