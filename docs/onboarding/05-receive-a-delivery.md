# 05 · Receive a delivery

## What this is for

A van arrives with a stack of cartons and a slip of paper on it. This is where you write
down what actually came, from whom, at what cost, and how many of each. One button press
turns that list into shelf counts and into purchase batches, and the batches are what the
till later sells out of and what your cost valuation is built from. Nothing moves on the
shelf before you press it.

## You need

- **Role.** The owner's account (administrator). This screen, the register and the drafts
  are all owner-only. A cashier who types any of these addresses does not get a "not
  allowed" message — they land back on the sign-in page, which looks exactly like a session
  that ran out.
- **Screen.** The **Receive Delivery** dialog. It opens on top of the Products & Inventory
  ledger: the **Receive Delivery** button in that ledger's top-right row of buttons, between
  *Import CSV* and *Purchase Receipts*.
- **Other ways in.** A row's *Restock* icon (the grey box-with-a-plus in the row's action
  column, green when you hover it) opens the same dialog with that product already on the
  first line, 24 units and its current cost filled in. Set the **Stock status** filter to
  *Out of stock* and tick rows, and a **Restock selected** button appears above the table
  that opens it in *Batch Restock* form instead. Note: the *Low & Out of Stock* tab does not
  bring that button up; only the *Out of stock* filter does.
- **The register.** The **Purchase Receipts** button on the same toolbar opens the ledger of
  everything already booked. It is a page of its own, not a dialog.
- **Data that must already exist.** Products in the catalogue. The line search only offers
  what is already a stock item; an empty catalogue answers
  *"The catalogue has no products to add yet."* A supplier name must come from you: the shop
  has no supplier list, no supplier page and no saved suppliers. Supplier is a line of typing
  on the receipt.

## Steps

### 1. See what has already been booked

![The Purchase Receipts register. Breadcrumb "Store Central > Stock Ledger > Purchase Receipts", heading "Purchase Receipts", the line "Every receipt that put stock on the shelf, newest first, with what it cost.", a "Back to Products" button, a Delivery drafts panel badged "0 DRAFTS" reading "No saved delivery drafts.", and below it the Receipt Ledger table badged "360 RECEIPTS" with columns Receipt, Received on, Purchased, Source, Supplier, Lines, Units, Cost, By. The newest row is a green PURCHASE receipt, received 04 Nov 2026 12:54, purchased 04 Nov 2026, no supplier, 2 lines, 36 units, GH₵ 199.20. The rows under it are violet IMPORTED OPENING BALANCE receipts of one line each. The footer reads "Showing rows 1–25 of 360 receipts" and "Page 1 of 15".](img/05-receiving/05-receipts.png)

Read this page before you book, not after. Every row is one booked receipt; the receipt code
in the first column is a link to that receipt's line-by-line detail, which shows what each
line still holds on the shelf. The **Source** pill tells you where the stock came from —
*Purchase* for a delivery you booked here, *Imported opening balance* for stock that arrived
with a CSV import, *Opening balance* for stock typed in when the product was created. The
**Supplier** column is an em dash when the name was left blank at booking; it can only be
filled in at that moment.

### 2. Fill in the delivery

![The Receive Delivery dialog open over the Products & Inventory ledger. Title "Receive Delivery", subtitle "Book one delivery, as many products as it carried.", a close X top right. An empty "PURCHASED ON" date box showing mm/dd/yyyy. A "SUPPLIER DELIVERIES" section with an "Add another supplier" button, one group holding a "SUPPLIER" box with the placeholder "Who sold these products" and an "INVOICE / REFERENCE" box with the placeholder "INV-0000" and a red bin icon. One line row: a focused "Name or code" box, a "Units" box, a "Unit cost" box with "Previous unit cost: GH₵" under it, a fourth box whose label is cut off mid-word, a bin icon, and preset buttons "+12" "+24" "+48" "+100". Below the group, "A blank selling price leaves that product's price where it is." and, in red, "Every line needs a product." A "CALCULATION & LEDGER IMPACT" panel reading "1 line(s) across this delivery", Units in 0, Delivery cost GH₵ 0.00, Retail at these prices GH₵ 0.00, Gross margin 0.0%, and "0 line(s) will change a store-wide selling price." In the footer, "Save draft", "Cancel" and a greyed-out "Book 1 line" button.](img/05-receiving/05-receive-dialog.png)

Work down the frame:

- **Purchased on.** The date on the supplier's paper. Leave it empty and the register's
  Purchased column shows an em dash; the *Received on* column is the clock time you book, and
  you cannot change it.
- **Supplier** and **Invoice / reference.** Free text, 255 characters each. The reference is
  the only place the invoice number can live, and it is not checked against anything.
- **The line row.** Type a name or a code in *Name or code*; a short list drops under the box
  after a moment of typing, each option showing the code, how many are on the shelf and the
  current price in `GH₵`. Click one. The box is replaced by the product's name and code with a
  **Change** link beside it, and the cost box fills with the product's present unit cost.
- **Units.** Type it, or use the preset buttons. Note what those buttons are: `+12`, `+24`,
  `+48`, `+100` **set** the units box to that number, they do not add it to what is already
  there. The plus sign is a label, not an operation.
- **Unit cost.** What this line actually cost you, per unit. It is required, and the last line
  for a product on this receipt becomes that product's cost on the ledger.
- **The fourth box** is *New selling price (optional)* — the frame shows its placeholder cut
  short by the width of the box. Type in it only if this delivery changes what customers pay.
  Left blank, the price does not move, exactly as the line under the group promises.
- **More lines, more suppliers.** *Add product to this supplier* puts another empty row in the
  same group. *Add another supplier* adds a whole group, and its own bin icon removes a group
  with all its lines.
- **Watch the panel.** Units in, delivery cost, retail at these prices and gross margin
  recalculate as you type, and the two counters tell you how many lines the delivery has and
  how many of them will move a price.

The three row warnings worth knowing: a row whose new price is under its own cost gets a rose
**below cost** pill; a price above the sellable ceiling gets **over the sellable cap**; the
same product typed twice inside one supplier group gets the amber line
*"Same product appears more than once for this supplier; check quantities and costs."*

### 3. Book it

This step ends at the button. There is no frame of the result: nothing in this manual was
booked while the pictures were taken.

What the button does, in words. **Book N lines** posts the whole dialog as one operation.
Either every supplier group on it books or none of them do — a bad line in group three stops
group one. When it succeeds, a small panel appears in the dialog's place with the title
*Ledger updated*, the line *"The stock table behind this dialog already shows the change."*, a
sentence counting the lines, the receipts and the units — one receipt code per supplier group,
so a three-supplier delivery makes three receipts, not one — and a **Back to ledger** button.
The ledger behind refreshes: the shelf counts go up, and any product whose line carried a new
selling price now shows that price everywhere the shop sells it. The register reloads too, and
the receipt you just booked is the newest row on it.

If you are not ready to book, **Save draft** keeps what you typed. Typing also saves itself a
moment after you stop; the only sign of that is a small grey line under the supplier groups
cycling through *Unsaved changes*, *Saving draft…* and *Draft saved*. A draft changes no stock
and no price. It appears as a row in the **Delivery drafts** panel on the register — supplier
names, line count, supplier count, "Last saved" — with **Continue** and **Delete**. No draft
was saved while the pictures were taken, so the panel in the frame is empty. Continue
reopens this dialog with your typed rows restored — including rows whose product has since
been removed; those come back as an unnamed row with an empty *Name or code* box, still
carrying the dead product behind it, so re-pick before booking. Drafts belong to the account
that saved them; another owner's register does not list them.

## When it goes wrong

- **The band at the top of the dialog.** Every booking refusal re-renders this dialog with a
  rose band reading `Nothing was saved. ` followed by the reason, and your typing is still in
  the rows — the row at fault comes back ringed in red. Real sentences, as the app writes them:
  - *"Line 2 has no product yet. Pick one from the search box."*
  - *"Line 1 needs a unit cost."*
  - *"Line 1 needs a whole number of units."*
  - *"Line 1 takes between 1 and 100,000 units."*
  - *"Line 1 has an unreadable unit cost."* / *"Line 1 has a unit cost that is too large."*
  - *"Line 1 names a product that is no longer in the catalogue."*
  - *"Add at least one product to the receipt."*
  - *"This dialog books at most 50 lines per receipt."*
  - *"Line 1 cannot sell above GH₵ 9999.99; checkout refuses a sale line bigger than that."*
  - *"Enter a purchase date as YYYY-MM-DD, or leave it empty."*
  - *"The receipt lines arrived incomplete. Close the dialog, reopen it and try again."*
  - *"The receipt could not be saved. Try again."*
- **The button that is not there yet.** In the frame above, **Book 1 line** is grey and
  unpressable, and the red line *"Every line needs a product."* is the reason. The booking
  button stays dead while any row is unnamed. It is not broken and there is nothing to click
  instead: pick a product on every row.
- **Batch Restock refusing a product that is not empty.** The **Restock selected** path only
  accepts depleted products. If one of the ones you ticked has gained stock since the list
  loaded, the dialog reopens titled *Batch Restock* with
  *"Some selected products could not be found or are no longer depleted. Refresh the list and
  try again."* Restock the ones that are genuinely at zero, or use the row's own *Restock* icon
  for the other — that path does not insist on zero.
- **A product whose counts disagree.** If a product's batches no longer add up to its shelf
  count, the service refuses to write to it at all, and the delivery band reads
  *Inventory is inconsistent for `<product name>`; reconcile it before writing.* — see chapter
  06 for what that lockout is and what it blocks.
- **Draft refusals** are not a band; they appear as the small rose text beside the grey save
  state: *"This delivery is too large to save."*, *"This delivery has already been booked."*,
  *"This saved draft could not be found."*, *"The draft could not be saved. Try again."* A
  draft that has been booked cannot be saved over; it is history now.
- **A supplier group that will not add.** *"Could not add a supplier group. Please try again."*
  or *"Could not add a supplier group. Check your connection and try again."* The button also
  simply greys out at the delivery's ceiling — 20 supplier groups, 50 lines.
- **The search finds nothing.** *"Nothing in the catalogue matches `<what you typed>`."* The
  picker is a short list, not the whole catalogue: twenty candidates at a time, so an
  ambiguous name means typing more of it.

## Notes & limits

- **A booked receipt cannot be edited. At all.** There is no edit control on the register, on a
  receipt's detail page, or anywhere else. That page is deliberately read-only — no form, no
  buttons, nothing to press except a link back to the register. If you booked the wrong
  quantity, cost or price, you do not correct the receipt; you correct the **batch** it created,
  with the adjustment dialog in chapter 06, or you book a second delivery line for what you
  missed. This is the single most important habit on this screen.
- **Booking is one action, not a preview.** There is no confirm step, no review screen, no
  "are you sure". The button writes. The one protection is that the dialog carries a single
  key for as long as it is open, so a double-tap or a slow network that sends the booking twice
  is recognised and lands as one receipt. Reopen the dialog and it is a new delivery.
- **The presets and the price box lie a little.** `+12` sets 12 rather than adding 12, and the
  *New selling price (optional)* placeholder is clipped by its own box at this width. The box
  works; read the totals, not the label.
- **A blank row shows "Previous unit cost: GH₵" with nothing after it.** The code means to hide
  that line until a product is chosen, and the row's own styling keeps it on screen anyway. It
  fills in the moment you pick something.
- **Prices are store-wide and instant.** A selling price typed here rewrites the product's price
  for every till and every future sale, not for this delivery only. The app records the old and
  new price on the batch, but **no screen anywhere shows that pair** — not the ledger, not the
  receipt detail, not the batch history. If you need the audit trail of a re-price, it is not in
  this product yet.
- **Cost follows the same last-line rule.** For a purchase, the product's cost on the ledger
  becomes the cost of the last line for that product on this booking. Two lines for one product
  with different costs is legal; the batch costs stay separate, the product cost is whichever
  line came last.
- **No supplier master exists; categories are a fixed list.** Supplier is nothing but typed
  text with no deduplication: "Kofi Textiles" and "Kofi Textiles Ltd" are two suppliers
  forever, and the register simply lists their receipts as separate rows, newest-first — it
  does not group them. Categories are the opposite: the shop ships with a fixed set, and the
  ledger's Category filter and the pill on each product row read from it.
- **Ceilings, stated plainly.** 50 lines and 20 supplier groups per dialog; 100,000 units per
  line; a selling price ceiling of GH₵ 9999.99 because the till refuses a bigger sale line.
- **The register pages at 25 receipts** and always newest-first. There is no search box on it,
  no date filter, no supplier filter. To find an old receipt you page, or you remember its code.
- **Closing the dialog.** *Cancel*, the X, the Escape key and a click on the dimmed
  background all close it. The backdrop is not a guard — it is a fourth close, and it
  behaves that way for every dialog in the shop, not just this one. Closing wipes the form
  off the page, so nothing you typed stays on the screen. What normally rescues your work
  is the draft autosave: less than a second after you stop typing, the dialog has written
  itself a draft, which is why a delivery lost to a stray backdrop tap usually reappears
  under **Delivery drafts** rather than where you left it. Close it inside that instant and
  the last keystrokes really are gone.
- **What this screen will never do:** undo a booking, split a delivery across days, record a
  returned or damaged line, attach the supplier's invoice file, or warn you that a product is
  already out of balance before you press Book.
- **Only the owner sees any of this.** A cashier has no route to the ledger, the dialog, the
  drafts or the register.

Related chapters: **04** for the ledger this dialog sits on, **06** for correcting a batch after
booking, **07** for products that should not have been restocked at all, **13** for the gaps this
chapter names.
