# 08 — Work the till

## What this is for

This is the counter. You tap a product, a line appears in the cart on the right, the money adds itself
up, and one button turns that cart into a booked sale with a receipt code. Everything the shop sells
leaves through this screen, and for a cashier it is the only working screen the shop has: past it they
get Help and their own account, and nothing else.

## You need

- **Either seat, arriving two different ways.** A signed-in cashier lands on the till automatically —
  the shop's opening page *is* the register for them, and their header carries only two items,
  **Point of Sale** and **Help**. The owner reaches the identical screen by clicking **Point of Sale**
  in the top navigation, which opens the register tab of the orders page. Same tiles, same cart, same
  buttons; only the takings label and the header differ.
- **A register role.** Both the owner seat (ADMIN) and a salesperson seat (SALEPERSON) may ring sales.
  Any other account is thrown out at the door.
- **Products with stock above zero.** The grid is built from those and only those, so a sold-out item is
  not greyed out in the list — it is simply not there.
- **Nothing else.** The cart is not saved anywhere. It lives in the browser tab you are looking at, and
  closing the tab throws it away. There is no held sale, no parked basket, no second till to reconcile
  against.

## Steps

Frames were shot on a machine with 358 sellable products and an empty cart. No sale was rung up while
this manual was written, so the frames below stop at the threshold of the sale itself; the part past it
is told in words and labelled as such.

**1. Get to the till.**

![A browser at 1440 wide showing the register as a signed-in salesperson sees it on opening the shop: a
header with the Noble Cosmetics brand, a highlighted "Point of Sale" item, "Help", an account chip and a
red "Log Out" button; below it a status bar reading "Register Open  Store #01 · <the signed-in name>",
"Your Takings: GH₵ 0.00" and "358 products sellable", with a "/ SEARCH" chip at the right; then a search
box, a four-column product grid, and a "Customer Cart" panel on the right.](img/08-till/08-hub-cashier.png)

For a cashier this is the whole working day. There is no hub to escape to, and nothing to learn besides
this frame and chapter 09; the only other things their header opens are Help and their own account.

**2. Read the bar above the grid, left to right.**

![The register at 1440 in the salesperson's seat: the status bar with "Register Open", "Store #01 ·
<the signed-in name>", "Your Takings: GH₵ 0.00" and "358 products sellable"; the search box reading
"Search products by name..." with a "PRESS /" chip inside it; product tiles with badges such as "LOW: 1
LEFT", "LOW: 2 LEFT" and "8 IN STOCK", each with a name, a price line such as "GH₵ 25.00" and a small
"+"; and on the right the "Customer Cart" panel marked "0 LINES", a greyed "Clear", the dashed box
"Cart is empty / Pick a product to start the sale.", then "Subtotal GH₵ 0.00", "Units 0", "Total Payable
GH₵ 0.00", a pale "Complete Sale • GH₵ 0.00" button and a pale "Void Cart" button.](img/08-till/08-pos-cashier.png)

This is the same screen as step 1, from the cashier's side again. The second frame was taken by asking for
the owner's address for the register and being handed back this page, which is the bounce the first bullet
of *When it goes wrong* describes. Nothing on it is new; it is the frame to read closer.

- **"Register Open"** is a green dot and a promise, not a switch. There is no open-and-close-the-day
  ritual anywhere in the shop; the till is open whenever you are signed in.
- **"Store #01"** is fixed text. The shop has no stores table and no second till, so the number is
  decoration beside your own name.
- **The takings figure** is the money booked *today* — and for a salesperson it is only their own sales,
  which is why this frame reads `GH₵ 0.00`. It is not a float, not a cash-drawer balance, and it says
  nothing about what you have banked.
- **"358 products sellable"** counts products holding more than zero stock. It moves when a delivery is
  booked or a sale completes; it is not the size of the catalogue.
- **"PRESS /"** is real: tapping the slash key anywhere *outside* a text field jumps the cursor into the
  search box, which is the fastest way to a known name on a busy counter. Inside a field the slash is just
  a character and nothing jumps.

**3. Know that the owner's copy of this screen says something different.**

![The same register at 1440 in the owner's seat: the header now carries five navigation items —
"Central Hub", "Point of Sale", "Products & Stock", "Orders", "Sales Reports" — plus "Help"; the status
bar reads "Register Open  Store #01 · <the signed-in name>" and "Today's Takings: GH₵ 162.00" beside the
same "358 products sellable"; the grid and the "Customer Cart" panel, including "0 LINES", "Cart is
empty", "Total Payable GH₵ 0.00" and the pale "Complete Sale • GH₵ 0.00", are unchanged.](img/08-till/08-pos-admin.png)

Two differences, and only two. The label reads **Today's Takings** instead of **Your Takings**, and the
figure behind it is the whole store's takings for today rather than one person's — `GH₵ 162.00` here
against `GH₵ 0.00` in the salesperson's frame two steps back, both captured on the same machine in the
same run, which is exactly the point: two people, one shop, two different numbers, and neither of them
wrong. The second difference is the header: the owner is offered the rest of the shop, the cashier is
not. Nothing about the cart, the prices or the buttons changes between the seats.

**4. Build the cart — this part is told in words, because no frame shows it.**

What you have in the frames above is the empty cart. Here is what happens when you use it, from the
same screen's behaviour:

- Tapping a tile, or its `+`, adds one unit. Tapping the same tile again adds a second unit to the *same
  line* — a product never appears twice in a basket.
- The line shows the name, `GH₵ <price> each`, a `−` and a `+` around the quantity, the line total, and a
  trash icon that removes the line. The `−` stops at 1: you cannot dial a line down to nothing, you
  delete it. The `+` stops at the stock figure the tile was carrying when you tapped it, and it stops
  without telling you — the button just goes dead.
- `Subtotal` and `Total Payable` are the same number — this screen's arithmetic has no discount field, no
  tax line and no rounding step. `Units` is not money at all: it counts the units in the basket, so three
  items at GH₵ 14.00 read Subtotal `42.00`, Units `3`, Total Payable `42.00`. On an empty cart all three
  read zero, which is how the two figures get mistaken for one.
- The header chip counts lines (`0 LINES` becomes `1 LINES`, ungrammatical but honest), and the
  `Complete Sale` button picks up the money in its own label, so the button you press reads
  `Complete Sale • GH₵ 42.00` on a GH₵ 42.00 sale.
- `Clear` and `Void Cart` do exactly the same thing to an unsent cart.

**5. Ring it, and read what comes back — also not pictured.**

`Complete Sale` posts the cart and replaces the cart panel with a settlement card. That card holds: a
green band reading `Success alert!` then `Order Number <code> totaling GHs <amount> was successful.
Thank you.`; a `Receipt` line showing `#NC-<code>`; the takings figure for the bar above, already
rewritten without a page reload; and two buttons — `Start New Sale`, which hands you back an empty cart,
and `Download Receipt`, which is chapter 09.

Two things a new cashier must be told plainly. First, **the sale is booked the moment that band
appears** — the stock is gone, the receipt exists, and nothing on this screen can undo it. Second,
**press once**. The register sends no anti-double-tap token, so a second tap on `Complete Sale` books a
second identical sale. If the customer's item genuinely needs two sales, fine; if it was a slip, the
only remedy is the owner's ledger and a fresh correction sale, because there is no un-book button.

**6. Work it on the phone.**

![A 390-wide frame of the register in the salesperson's seat: a collapsed header with the brand, an
account chip, a theme button and a hamburger; the status bar wrapped onto two lines reading "Register
Open  Store #01 · <the signed-in name>" and "Your Takings: GH₵ 0.00   358 products sellable" with the
"/ SEARCH" chip; the search box with "PRESS /"; a two-column product grid with the same badges and price
lines; and below the grid, not beside it, the "Customer Cart" panel with "0 LINES", "Cart is empty /
Pick a product to start the sale.", "Subtotal", "Units", "Total Payable GH₵ 0.00", the pale
"Complete Sale • GH₵ 0.00" and "Void Cart".](img/08-till/08-pos-phone-cashier.png)

The cart is *below* the grid here, so on a phone you scroll to it — and once a line exists a bar appears
at the bottom of the screen carrying the basket summary and a `Pay` button, so you rarely need to. That
bar is not in this frame: with an empty cart and the panel not opened, the bar is hidden by design.

**7. What the screen is made of, with its clothes off.**

![The register fragment loaded at its own address, unstyled: plain text and oversized icons in document
order — "Register Open Store #01 · <the signed-in name>", "Today's Takings: GH₵ 162.00", "358 products
sellable", "/ Search", the search box with "Press /", a stack of product tiles each showing a large "+"
over a line of text such as "Low: 1 left 717 Hair Relaxer (Large) GH₵ 25.00", then the heading
"Customer Cart", a "Clear" button, "Cart is empty", "Pick a product to start the sale.", "Subtotal",
"Units", "Total Payable", "Complete Sale • GH₵", "Void Cart", and last of all three further buttons
labelled "In cart GH₵", "Back to products" and "Pay".](img/08-till/08-register.png)

This is the same register stripped of its stylesheet and its header, which is what you get if you type
the fragment's own address into the bar. It is worth one look for two reasons: it shows the true order
of the controls, and it exposes the phone bar — `In cart`, `Back to products`, `Pay` — as part of every
register, laptop or not. Nothing here is a different screen; do not use this address to work a sale.

## When it goes wrong

- **A cashier who types the owner's register address is bounced, and is not told why.** The tab address
  the owner uses is gated to the owner seat. A signed-in salesperson who types it is carried through the
  sign-in address and straight back to their own till — the opening page, the register, with no message
  anywhere saying why. They do not see the sign-in card: the shop only shows that when the session is
  genuinely dead, which is the next bullet. Nothing has broken, and their own till never moved.
- **A session that dies mid-sale swaps the sign-in card into the cart panel.** Nothing redirects the
  partial, so a cashier who has been left too long sees a login form inside the register. Sign in again
  in that panel and the page carries on; the cart itself, being browser-local, survives only if you
  have not reloaded.
- **The empty cart refuses to be completed, and the refusal is a disabled button, not a message.** With
  no lines, `Complete Sale`, `Clear` and `Void Cart` all sit pale and unclickable, as they do in every
  styled frame above. Step 7's unstyled frame is the exception, and it proves the point: there the same
  three are at full strength, because the paleness is a rule the stylesheet adds and not something the
  refusal does to the button. If the button is pressed by other means, the panel answers
  `No items in the cart. Add items to the cart and make payment.`
- **A stale cart is refused at the counter, in a red band.** The prices and stock figures in your cart
  were copied when you tapped. If somebody restocked or re-priced in the meantime, the sale comes back
  as `Danger alert! The sale could not be completed: Only 2 units are available.`, or
  `Danger alert! The sale could not be completed: The cart price changed. Refresh the register.`, or,
  when the shop's own numbers disagree, `Danger alert! The sale could not be completed: Inventory is
  inconsistent for <product name>; reconcile it before writing.` In every case the lines stay in the
  cart so you can fix them — the refusal does not clear your work.
- **A cart the shop cannot read is refused before anything is touched:**
  `Danger alert! The cart could not be read. Reload the register and run the sale again.` A rarer one,
  `Danger alert! The sale could not be completed. Try again.`, means the database said no; the money and
  the stock are untouched, but do not assume the sale is lost — check the ledger before ringing it twice.
- **The ceiling on a line says nothing.** The `+` on a cart line greys out at the stock figure the tile
  carried, with no tooltip and no message. It is not stuck and it is not a bug you can tap through; the
  shop genuinely will not sell more than that right now.
- **The product you were asked for is not on the grid.** Zero stock means invisible, not dimmed. Say
  "we are out", and leave the count to be fixed from the stock screens — a cashier cannot reach them.
- **There is no reprint button on the till, and no refund button anywhere.** After you leave the
  settlement card, this screen has no path back to a receipt at all.

## Notes & limits

- **"Void Cart" voids nothing.** It empties an unsent cart and is the same action as `Clear`, under a
  different word. The name is the worst label on this screen: it invites a cashier to believe a booked
  sale can be undone here. It cannot. No refund, no void, no edit and no re-attribution of a completed
  order exists in the interface — a booked order is permanent and the only correction is another sale,
  which is a decision for the owner.
- **There is no tender type and no change due.** No cash / MoMo / card choice, no "amount tendered", no
  change figure, no split payment. The shop records that you were paid the total, nothing about how. The
  hub card that advertises "accept Cash, MoMo, or Card payments" is describing a wish, not this screen.
- **Barcode scanners are not integrated.** The search box matches a product name or its code as typed
  text; a scanner that emits the code and Enter will land on the right product only because it looks
  like a typed search. There is no dedicated scan field, and no barcode is printed on the tiles.
- **The grid is twelve tiles at a time.** Scrolling pulls in the next twelve as the last tile comes into
  view, which is why the three desktop frames above show twenty-four tiles of the 358 while the phone
  frame and the unstyled frame show the first twelve. There is no pager to click and no "load more"
  button; if you stop scrolling, the list stops arriving.
- **Prices are read live, and charged live.** The tile shows the product's current selling price and the
  till re-checks it against the shop's own figure when you book, so the price on the paper is the shop's
  price, not the one you saw. If they disagree, the sale refuses rather than quietly charging the other
  amount.
- **No customer is ever captured.** The cart has no name, no phone, no account. Every sale is a walk-in,
  and the receipt says so in the ways chapter 09 covers.
- **The takings figure is a today-only, local-date figure.** The clock the shop runs on is UTC, which in
  Ghana is the same as local time, so the number rolls over at midnight and never shows yesterday. It is
  not a cash reconciliation and there is no float to count.
- **The money symbols are spelled three different ways across the shop, and this screen uses one of
  them.** The register writes `GH₵` everywhere — the takings chip, the tile prices, Subtotal, Total
  Payable, the button. The success band that appears after a booked sale writes `GHs` in its sentence,
  and the receipt paper writes `(GHS)`. Same currency, three spellings; do not try to make a cashier
  remember which is which, and do not "correct" the quotes above.
- **The tiles without a photo show two letters**, taken from the start of the product's *name* — so
  `Abana` and `ABC Relaxer (Large)` both read `AB`, and `717 Hair Relaxer (Large)` reads `71`. The shop's
  own code for the product plays no part in those letters. It is a placeholder, not a code; the real code
  is on the product's own ledger page, which a cashier cannot open.
- **What only the owner can see, from this same screen:** the store-wide takings figure, the ledger, the
  reports, the stock screens and every other person's sales. A cashier sees their own figure under
  `Your Takings` and nothing belonging to anyone else — receipts of other cashiers do not exist for
  them, even by address.
- **This screen will never:** hold a basket between visits, take a deposit, print anything itself,
  adjust a stock count, look up a customer, or tell you that something is out of stock before you
  search for it.

Related chapters: 01 (the sign-in page a dead session lands on, and the one a bounced cashier never sees),
02 (the owner's hub, which is where the rest of the shop lives), 05 and 06 (how the stock figures on these
tiles get filled), 09 (the
receipt a booked sale produces), 10 (the ledger a cashier cannot reach but the owner checks against
this screen), 13 (the promises this screen's labels still make).
