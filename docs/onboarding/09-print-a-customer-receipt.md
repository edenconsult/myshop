# 09 — Print a customer receipt

## What this is for

When a customer asks for a receipt, or when you handed one over and it went in a pocket torn in half,
this is the paper: a narrow 80 mm roll receipt with the shop's address at the top, the lines in the
middle and the total under a rule. "Printing" in this shop means **downloading a PDF file** — there is
no print dialog, no printer queue and no choice of paper size anywhere in the interface.

## You need

- **A booked sale.** A cart that has not been completed has no receipt and cannot be given one. The
  receipt is a property of the order, not of the till.
- **Either seat, with very different reach.** A salesperson gets exactly one entry point: the
  `Download Receipt` button on the settlement card, in the few seconds after the sale is booked. The
  owner gets two, and both of them are on screens a cashier cannot open: the receipt inspector in the
  ledger, and the printer icon on a report row.
- **A machine that saves a file.** The download is the whole feature; if the browser is set to open PDFs
  inside the tab, the paper appears on screen and still has to be sent to a printer by whoever holds it.
- **One honest caveat about this chapter.** No receipt was downloaded while this manual was being
  written, and no sale was rung up, so **there is no picture of a receipt or of a receipt PDF in these
  pages**. The one frame below shows the button that produces it. The paper itself is described from the
  template it is built from, and you will meet the real thing the first time you press the button on a
  booked order.

## Steps

**1. The frame that exists: the inspector, with the button in it.**

![The owner's Orders & Receipts Ledger at 1440 wide with a receipt card open on the right. The ledger
behind it shows four tiles — "TODAY'S RECEIPTS 2", "TODAY'S REVENUE GH₵ 162.00", "AVERAGE ORDER VALUE
GH₵ 81.00", "TODAY'S PROFIT GH₵ 40.95" — a search box reading "Search receipt code (e.g. A1B2C3)..." with
"PRESS /", an "All Cashiers" dropdown, a date box reading "11/04/2026", a pale grey "Print Batch" button
(enabled — it is just styled quietly) and
a green "New Sale (POS)" button, then two rows: "#LR16DR" at "12:57", basket "ABC Relaxer (Small) +1
more", cashier "admin", total "GH₵ 30.00", and "#GJPMR5" at "12:56", basket "Abana +1 more",
"GH₵ 132.00". The open card is headed "Order #LR16DR" with "Nov 4, 2026 • 12:57" under it and a small
cross at its right; then "CASHIER admin" beside "CUSTOMER Walk-in Customer"; a two-column list headed
"ITEM DESCRIPTION" and "SUBTOTAL" holding "ABC Relaxer (Small) / Qty: 2 / GH₵ 20.00" and
"Active Men Cream / Qty: 1 / GH₵ 10.00"; then "Items sold 2", "Total Paid GH₵ 30.00"; and at the bottom
one full-width green button reading "Download Receipt PDF".](img/09-printing/09-order-inspector.png)

That button is the owner's reprint path. It is the only receipt-related control this manual can show you.

**2. The three ways to that file, in words.**

- **Straight after the sale**, on the till's settlement card: a plain outlined button reading
  `Download Receipt`, under `Start New Sale`. This is the salesperson's only one.
- **From the ledger**, as in the frame above: click a receipt row, then `Download Receipt PDF` at the
  foot of the card.
- **From the reports screen**, on any row of the transaction ledger: a small printer icon whose hover
  text is `Print #<code>` and whose hidden label reads `Print receipt <code>`. It sits beside an eye
  icon that goes to the ledger instead.

All three open the same document for the same order. They differ only in who is allowed to see them.

**3. What lands on the machine.**

A file named `Invoice-<code>-<stamp>.pdf`, where `<code>` is the six-character receipt code and `<stamp>`
is the day, month, year, hour, minute and second **of the reprint**, in the form `04112026143207`. Two
consequences worth knowing: the file is called an *Invoice* even though every button calls it a
*Receipt*, and saving two copies of the same receipt gives you two different filenames, so the name
tells you nothing about when the sale happened. The date printed on the paper is the sale's own time and
never moves.

**4. The anatomy of the paper, top to bottom.**

Not pictured; this is what the template puts on the roll, in this order, in this install's real wording.

1. **The company block**, centred, small: the shop name in capitals, then the location line, then
   `Tel: ` and the phone number. On this install those read `Noble Cosmetics Ltd.`,
   `Atebubu Bayere Bode Junction`, `Tel: +233 24 833 1063`. A fourth line, `Email: `, appears **only if
   the shop's email address is filled in** — and here it is blank, so no email line prints at all.
2. A dashed rule across the paper.
3. **The meta block**, left-aligned: `Receipt No.: LR16DR`, then `Date:` in `day/month/year hour:minute`
   form, then `Served by:` and the cashier's name, then `Customer:` **only when a customer name was
   recorded** — which the till never does, so that line never appears on a counter sale.
4. Another dashed rule.
5. **The line table**, four columns headed `Item`, `Qty`, `Unit`, `Amount`. For the receipt open in the
   frame above, the paper would carry `ABC Relaxer (Small)` with `2` and `20.00`, then
   `Active Men Cream` with `1` and `10.00` — those are the frozen line amounts the screen shows. The
   `Unit` column prints whatever each product's shelf price is **now**, so both `Unit` cells read
   `10.00` here only while neither price has moved; see the warning under "When it goes wrong". Names
   are not truncated: a long
   name wraps onto as many lines as it needs and the paper grows to fit.
6. **The total**, under a solid rule, in bold: the words `TOTAL (GHS)` on the left and the figure on the
   right. This is the only place on the whole document where the currency is named, and it is spelled
   `GHS` — the screen above it spells the same money `GH₵`, and the success banner on the till spells it
   `GHs`. Every number in the table itself is bare: no `GH₵`, no thousands comma.
7. Another dashed rule, then **the footer line**, centred: on this install
   `Goods sold are not returnable. Thank you for your patronage!`
8. **The colophon** at the cut edge, in the smallest type on the paper: the shop-system logo beside the
   developer block — `Eden Creative Systems`, `Tel: +233 24 816 0391`, `Email: berkojohnson@gmail.com`,
   `Web: ecreativesys.com`. This is not removable from the till; it is a setting, and it is deliberately
   the last thing on the roll.

**5. Feed it, cut it, hand it over.**

The document is one long page 80 mm wide, sized by hand rather than by content: a fixed allowance for the
head, the meta block, the rules and the footer, plus a measured strip for each wrapped product name, plus
the colophon's own allowance, with a floor of 80 mm so a one-line sale still comes out as a recognisable
receipt instead of a scrap. Nothing in the interface lets you choose a width, a printer or a number of
copies. On a machine wired to a thermal roll, open the PDF and print it as you would any file; on a
machine that only has A4, the same sheet usually comes out as a narrow column down the page — but where
it lands on that A4 is the printer driver's choice, not something the shop controls.

**6. Reprint as often as you like.**

Reprinting reads the order and writes the paper. It changes nothing: no stock moves, no stored line is
re-priced — though the printed `Unit` column is re-read from the current price, see "When it goes
wrong" — the sale's own time is preserved, and the ledger row is untouched. The owner can do this all
day. The salesperson cannot do it at all after the settlement card is gone — see the next block.

## When it goes wrong

- **The till has no reprint button, and this is the one cashiers get caught by.** Once `Start New Sale`
  is pressed, or the page is reloaded, or the tab is closed, the receipt link is gone from the register
  for good. There is no "today's sales" list on the cashier's screen, no history, nothing to click. The
  customer who comes back an hour later has to be sent to the owner, or the owner has to give them a
  print from the ledger.
- **The label on the button and the name of the file disagree.** `Download Receipt PDF` produces
  `Invoice-LR16DR-04112026143207.pdf` — the stamp is whenever you happened to click it, not the sale's
  time. Nobody is being charged twice; it is the same document under a different word.
- **"Print" never prints.** No screen in the shop opens a browser print dialog, and no stylesheet here
  is written for one. `Print Batch` and the reports printer icon sit on owner-only screens, so it is
  the owner who clicks twice if they expect a dialog; the till's `Download Receipt` behaves the same
  way. It is a download every time, for every document in the shop.
- **A salesperson who guesses somebody else's receipt address gets a not-found page, not a refusal.**
  Receipts are filtered to the cashier's own sales before they are looked up, so another person's
  receipt does not exist as far as that account is concerned — the same Django not-found page a
  mistyped code gets. This install runs in debug mode, so that page is Django's own verbose
  not-found screen; on a production install it would be a bare error page.
- **The `Unit` column can lie about the sale.** `Amount` is the money frozen at the moment of the sale;
  `Unit` is re-read from the product's **current** price each time the paper is printed. If a price was
  changed after the sale, a reprint shows a unit figure that no longer multiplies into the line, while
  the total still comes out right. Quote the `Amount` column and the total to a customer, never the
  unit.
- **`Served by` prints the name backwards compared with the rest of the shop.** The paper uses the
  account's last name then first name, while the header, the ledger and the inspector use first then
  last. An account with no names recorded prints `Served by` followed by nothing at all — the username
  is not a fallback on paper, though it is on screen.
- **The paper has no empty state, the screen does.** The till will not create a sale without at least
  one line, and a receipt line cannot be deleted out from under an order, so this is a corner you should
  never reach — but if an order ever arrives with nothing in it, the printed table is headers and rules
  over a total of `0.00`, with no apology, while the inspector on screen says
  `This receipt has no recorded line items.`
- **The old after-hours hole is closed, and you should not repeat the warning.** An earlier build hid
  the `Download Receipt` button for any sale booked outside 06:00–20:00, which left a late customer with
  no reprint entry point at all. The current build does not gate that button by time: the check behind it
  counts that cashier's orders for the day with no hour bounds, and since the sale just booked is always
  in that count, the button appears whatever the clock says. The window only closes once that change is
  deployed, so if your install still hides the button at night you are on the older build, and the old
  warning applies to it.
- **The blank email is invisible until you look for it.** With the shop's email unset, the paper loses
  its `Email:` line and the roll loses its allowance for it, so a reprint after filling the address in
  produces a slightly longer sheet than the one before. Nothing on the till warns you of either.

## Notes & limits

- **Booked orders are immutable.** There is no refund, no void, no partial return, no line edit, no way
  to move a receipt to another cashier, and no way to add a customer name after the fact. The only thing
  the shop will do to a completed sale again is print it. A wrong sale is answered by ringing a new one
  and letting the owner correct the stock count from the inventory screens — a decision for the owner,
  not the counter.
- **The receipt carries no tender information.** No "Cash", no "MoMo", no reference number, no card
  last-four, no change due. The shop never records how it was paid, so no receipt can ever say.
- **No tax line, no VAT, no discount line, no signature line, no loyalty, no barcode or QR, and no
  return policy beyond the one footer sentence.** That sentence is a setting, not a rule the system
  enforces — the paper says goods sold are not returnable and the software has no view on whether they
  are.
- **The code is written three ways across three screens.** The settlement card on the till shows
  `#NC-LR16DR`; the inspector heading shows `Order #LR16DR`; the paper shows `Receipt No.: LR16DR`. Six
  characters, dressed three ways — and it is the bare six characters that the ledger searches on.
- **The number in a receipt's address is decoration.** Every reprint link carries a second value. On
  the settlement card it is the cashier's own count of their sales that day; from the ledger and from
  the reports it is simply the row's position on the page. The
  paper never reads it, so the same receipt prints identically whichever of those numbers reached it.
- **The paper is monospace and unadorned on purpose.** It is laid out for a thermal head that prints
  dots only: no filled bands, no grey, no colour, hairline rules, and column widths budgeted so that the
  `Amount` column cannot be pushed off the edge. It will not look like the screen, and it is not meant
  to.
- **Long names make a long roll, not a smaller font.** Nothing shrinks to fit; the sheet length grows.
  A six-line sale with long names is a noticeably taller receipt than the two-line one in the frame.
- **What only the other role can see:** the owner sees every receipt in the shop, in the ledger and the
  reports, and can reprint any of them; a salesperson sees only their own, and only through the button
  that appears once, immediately after their own sale. A salesperson has no screen in this shop that
  lists the receipts they have already printed.
- **Where the real paper lives:** this manual ships no sample receipt, no day-batch sheet and no report
  PDF, because none was downloaded. The first receipt anyone on this team reads is one they print
  themselves from a booked order.

Related chapters: 08 (the sale that creates the receipt, and the settlement card that is a cashier's only
entry point), 10 (the ledger where the owner finds any receipt to reprint), 11 (the report row with the
printer icon), 13 (the gaps: no refunds, no tender type, no true print path).
