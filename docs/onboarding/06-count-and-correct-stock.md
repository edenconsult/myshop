# 06 · Count and correct stock

## What this is for

You walked to the shelf, counted the boxes, and the number on the screen is not the number in
front of you. This is where you tell the shop the truth: which delivery that stock came from,
whether you are **Short** or **Found**, by how many, and why. The correction moves the batch and
the shelf count by the same amount, so the two never drift apart, and it is written down with your
name and your reason on it.

## You need

- **Role.** The owner's account. Both dialogs here are owner-only; a cashier who reaches either
  address is bounced to the sign-in page with no explanation.
- **Screen.** Two dialogs, both opened from a row of the Products & Inventory ledger:
  - **Adjust Stock Count** — the stock number itself is the button. It sits in the
    *Current stock* column, a grey pill showing the count, and its hover tip reads *Adjust
    counted stock against a batch*.
  - **Batch History** — the small tag icon in the row's action column, tip *Batch history*.
- **How to get there.** Sign in as the owner, open **Products & Stock**, find the product (the
  search box takes a name or a code, and the `/` key jumps the caret into it). Click the number.
- **Data that must already exist.** For a correction, at least one **open batch** on that
  product — a receipt line that still has units left in it. Stock typed in when the product
  was created counts: that typing is booked as an opening receipt, so it stands behind the
  count as a batch like any delivery does, and you can correct against it. It is the amber
  ESTIMATED batch in the frame below. Only a product whose batches have all sold out opens
  with *"No open batches. Restock the product first."* — sold-out batches are not listed
  here — and then there is nothing to correct against.
- **A reason, in your own words, before you press anything.** It is not optional and the shop
  keeps it permanently.

## Steps

### 1. Correct the count against a batch

![The Adjust Stock Count dialog open over the Products & Inventory ledger. Title "Adjust Stock Count", subtitle "Correct the counted stock of Active Men Cream against an open batch.", a close X top right. One batch row, its radio dot filled: "04 Nov 2026 · GH₵ 6.00 / unit" with an amber ESTIMATED pill, and "5 left" at the right. Below it two buttons, "Short" filled red and active, "Found" grey. Under those a stepper: a minus button, the number 1, a plus button. A "REASON" label over an empty single-line box with the focus ring on it. The line "Shelf total: 5 · a correction moves this batch and the shelf count by the same amount." In the footer, "Cancel" and a green "Save adjustment" button.](img/06-stock-count/06-adjust-dialog.png)

Work down the frame:

- **The batch rows.** One row per open batch, oldest delivery first, and the oldest is
  already selected for you — the dots are one-choice-at-a-time, so a correction always names
  exactly one batch. The selected one is the batch the till has been selling out of, so it is
  nearly always the right one. Each row tells you when it arrived, what it cost per unit in
  `GH₵`, and how many units it still holds. Only batches with units left are listed; a
  depleted batch is not correctable here, and you will see it in step 3 instead.
- **Short or Found.** *Short* means the shelf has fewer than the shop thinks. *Found* means more.
  **Read this before you press anything: the dialog opens on *Short* with 1 unit already in the
  stepper.** A reason typed and a quick tap on Save records one unit short. Tap *Found* first if
  you are counting stock in.
- **The stepper.** Minus and plus around a number box. The count is whole units, at least 1, and
  the box accepts up to 100,000. There is no zero: a correction of nothing is not a correction.
- **Reason.** Free text, up to 500 characters. Write what a stranger would need in six months —
  *"3 tins crushed in the move, thrown out"*, not *"adjustment"*.
- **The shelf total line** is the number you are arguing with. It is the ledger's count, live,
  and it is the number the correction will move.

### 2. Save it

This step ends at the button. There is no frame of the result: no correction was applied while
these pictures were taken.

What happens, in words. The dialog closes and the ledger row behind it is replaced with a fresh
copy of itself — the stock number now showing the corrected count, and the status pill
(*In stock*, *Low*, *Out of stock*) recalculated against the product's low-stock threshold. Only
that one row is redrawn. The valuation tiles above the table keep their old figures until the
page itself reloads — a browser refresh, or anything that re-books the ledger, such as a
delivery — and a filter, a sort or a page turn redraws the rows but not the tiles. So do not
read a stale *Stock Valuation* as a sign your correction did not land; the row is the truth.
Nothing is confirmed to you in a banner: the changed number **is** the confirmation, which is
why the dialog closes on a saved arrival and stays open on a refused one.

### 3. Check the history behind the number

![The Batch History dialog open over the Products & Inventory ledger. Title "Batch History", subtitle "Every batch behind Active Men Cream, newest receipt first.", a close X top right. A table with columns Received on, Unit cost, Received, Sold, Adjusted, Remaining. One row: "04 Nov 2026 12:51" with a grey "IMPORTED OPENING BALANCE" pill and "Line 1" beneath it, unit cost "GH₵ 6.00" with an amber ESTIMATED pill, received 6, sold 1, adjusted 0, remaining 5. Under the table, "Written-off batches stay listed, so the history behind a shelf count is complete." In the footer, a green check and the line "Sum of batches 5 · shelf count 5", and a "Close" button.](img/06-stock-count/06-batches-dialog.png)

This dialog is read-only and that is the whole point: no form, no buttons except **Close**
and the X at the top. It lists every batch the product has ever had, newest receipt first,
including depleted ones, which carry a rose **Depleted** pill on their remaining figure.
The three middle columns are the
reconciliation — received, sold out to customers, and the net of every adjustment anyone has made
against that batch, in green when it is a count-in and rose when it is a count-out.

The footer is the line to read after any correction: **Sum of batches · shelf count**. When the
two agree you get a green check and the two numbers. When they do not, you get a warning icon and
the sentence *"— out of balance; restocks and stock adjustments for this product are blocked until
the counts agree"*. See below.

## When it goes wrong

- **The dialog opens with no rows.** Just the grey band *"No open batches. Restock the product
  first."* There is no batch to correct against, so the only way forward is chapter 05. The
  Reason box is marked required, so with nothing typed there the browser stops you; once you
  have typed a reason, pressing **Save adjustment** anyway gets you *"Select a batch and enter
  a whole-number correction."*
- **You go deeper than the batch holds.** Shorting a batch by more than its remaining units is
  refused with *"The correction would make stock negative."* — even when the product's total
  shelf count would still be positive, because the other units live in a different batch.
  Select a different batch — the one with room.
- **No reason.** The Reason box is marked required, so the browser stops the save before the shop
  is ever asked; the box is where the caret is when the dialog opens. If a reason of any kind
  does reach the shop and turns out to be empty, the sentence is *"A reason is required."*
- **The batch you were looking at has gone.** Selling the last units does not delete a batch,
  it empties it — and an emptied batch still exists, so shorting it comes back as *"The
  correction would make stock negative."* A batch that has actually been deleted never gets a
  reason sentence from this screen: the shop checks the batch before your numbers are even
  read, and the check comes back as an error page the dialog cannot show you, so the dialog
  stays open on its standing *may be stale* band instead — see *The band that means something
  else* below. The sentence
  *"The selected batch does not exist."* is real, but it belongs to the split second between
  that check and the write — a race, not a refusal you will meet.
- **The product is out of balance.** Both this dialog and the Receive dialog refuse to write to a
  product whose batches no longer add up to its shelf count, with
  *Inventory is inconsistent for `<product name>`; reconcile it before writing.*
- **Where the sentence appears.** A refusal does not come back as a page. The ledger row's stock
  pill turns amber and carries the sentence, and the dialog **stays open with your reason and
  units still typed** and copies that same sentence into a rose band at the top of itself. The
  amber pill on the row removes itself after about six seconds — if you were looking at the table
  instead of the dialog, the reason is gone by the time you turn back.
- **The band that means something else.** If the save never reached the shop at all — a
  dropped connection, or the server answering with an error — the band keeps its own standing
  text instead of a reason: *"Nothing was saved, and the batch list behind this dialog may be
  stale. Close it and open Adjust Stock Count again to load the current batches."* Read that as
  "we could not find out", not "the shop said no". An expired session is different and worth
  knowing: the shop redirects the silent background save to the sign-in page, the dialog reads
  that answer as one with no error in it and **closes**, and the sign-in page lands in the
  table where the row was. Nothing warns you. If the dialog vanished and you are staring at a
  sign-in box, sign in again and check the count before you correct twice.
- **A database fault** is answered with *"The stock correction could not be saved."* and nothing
  else. Try once more; if it repeats, it is not your typing.
- **The number the app cannot accept.** Zero or an over-big figure comes back as *"Enter a
  non-zero valid quantity."*; a count-in that would push the product past the shop's ceiling
  comes back as *"The correction exceeds the stock limit."* A fraction or a non-number never
  reaches those checks — the dialog turns the box into a whole number first, and when that
  fails you get *"Select a batch and enter a whole-number correction."* The sentence *"Enter a
  whole number."* exists in the shop's code, but this screen cannot produce it. The stepper
  makes zero and fractions very hard to reach anyway.

## Notes & limits

- **This corrects a count. Nothing else.** It will not change a cost, a price, a supplier, an
  invoice reference or a date. The batch keeps the cost it arrived with; the corrected units are
  still valued at that cost, which is why a correction moves the shop's cost valuation.
- **Corrections are permanent and cumulative.** Each one is a record with the batch, the units,
  your reason and your name. The Adjusted column is their running total. There is no undo, no
  delete, no edit of an adjustment, and no list of them anywhere except as that single summed
  column — you cannot see who made which of the four adjustments behind a `-4`.
- **ESTIMATED is a real flag, not a shrug.** A batch cost carries the amber **estimated** pill when
  the cost was never confirmed by a booked purchase — stock that arrived as an opening balance
  typed in at creation, or through a CSV import, is estimated. It means the money figures built
  on that batch are provisional. The tag is shown on batch rows here and on a receipt's detail
  page; the split between confirmed and estimated cost is carried into the sales reporting, where
  the report CSV has separate estimated columns. A purchase booked through chapter 05 is never
  estimated.
- **FIFO, in shop words.** The till sells the oldest batch first, which is why the oldest open
  batch is pre-selected here. Because cost is frozen per batch, the shelf's cost value is the sum of
  each remaining batch times its own cost — not the product's cost field times the count. Correct
  the wrong batch and the total units still come out right while the valuation quietly drifts from
  what the shop actually paid.
- **The out-of-balance lockout has no self-service way out.** This is the honest one: the footer
  announces the block, and both screens that could change a count — this dialog and the Receive
  Delivery dialog — then refuse to touch that product. Nothing in the shop reconciles it for you.
  It should not happen in normal use; when it does it is a data fault, and it needs the person who
  maintains the install. Chapter 13 lists it as a gap for the owner to decide on.
- **Stock is typeable exactly once: when the product is created.** The Add-product dialog has an
  *Initial Physical Stock (Units)* box — chapter 03 photographs it — and whatever you type there
  is booked as an opening receipt, a real batch behind the number, correctable here like any
  other. After creation, no. The edit dialog has no stock field to type in: its *Current Shelf
  Count* frame carries no box, and the save re-reads the true count from the ledger whatever a
  form tries to hand it. The ledger number itself is a button rather than a field, on purpose.
  A count that has drifted is **corrected**, never retyped: through this dialog or through a
  booked receipt, so that every unit on the shelf keeps its paper trail. If you were hoping to
  just overtype the figure: you cannot, and that is the design.
- **Batch History will never let you act.** No restock button, no correct button, no link to the
  receipt that created a batch from here — read the numbers, press Close.
- **The two dialogs answer different questions.** *Adjust Stock Count* is "what do we actually
  have?"; *Batch History* is "where did it come from?". Correcting without checking the second is
  how owners end up with a right total in the wrong batches.
- **Only the owner sees either dialog.** A cashier cannot open the ledger, so they cannot report a
  count; they have to tell you and you have to make the correction. Nothing a cashier sells is
  ever adjusted from the till.

Related chapters: **05** for the delivery that creates the batch you are correcting, **04** for the
ledger and the valuation these numbers feed, **11** for the estimated-versus-confirmed split in the
reports, **13** for the lockout with no way out.
