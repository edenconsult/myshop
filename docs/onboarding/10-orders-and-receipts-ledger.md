# 10 — The orders and receipts ledger

## What this is for

Every sale the shop rings up becomes a receipt with a short code, and this is the book of them. When a
customer phones about a purchase, when the owner wants to know what a particular cashier took in on a
particular day, or when a receipt needs reprinting, you come here and look it up. It is also where the
day's takings are checked against what the till said it took.

## You need

- **The owner seat (ADMIN).** This tab is gated to the owner. A cashier who reaches its address is sent
  back to the sign-in page — see "When it goes wrong".
- **The screen: the Orders tab.** It is one of the three modes of the same page, opened by the top
  navigation item **Orders** (the tab only appears in an owner's navigation). Other ways in: the hub's
  *Orders & Receipts* card via **View All Orders** or **Find Receipt**, the **Orders Ledger** button on
  the reports screen, and the **Sales Reports** button that sits on this screen's own header going the
  other way.
- **Data that must already exist:** at least one booked sale. The ledger only ever shows receipts that
  were actually rung up at the till; nothing here is typed in by hand.
- The list shows **10 receipts per page**. Only the register grid pages differently, at 12; the
  product ledger works off the same ten as this list.

## Steps

Two frames: the Orders tab, which every step below happens inside, and the legacy screen at the end
of Notes & limits. The Orders frame keeps its shape as you filter — only the receipt list and the
right-hand panel move; the four tiles stay on today.

![The Orders tab: a header row with the page title and three buttons; four KPI tiles across the middle;
a filter bar with a search box, a cashier dropdown, a date box and Print Batch; below, a receipt list on
the left and a "Select a receipt" panel on the right.](img/10-orders/10-orders.png)

**1. Read the four tiles before you read anything else.**

In the frame they read `TODAY'S RECEIPTS 2` with `1 cashier on sales today` underneath, `TODAY'S REVENUE
GH₵ 162.00` with `No revenue recorded yesterday`, `AVERAGE ORDER VALUE GH₵ 81.00` with `~6.0 units per
basket`, and `TODAY'S PROFIT GH₵ 40.95` with `25.3% gross margin on today's revenue`. The revenue and
profit tiles carry a thin green progress bar; when there is nothing to compare against the bar is grey
and empty, as it is on the revenue tile in this frame.

**2. Narrow the list with the two filters on the right of the search bar.**

The dropdown reads `All Cashiers` and lists every account by name; the date box reads `11/04/2026`.
Change either and the list reloads itself — there is no Search button to press. The list header follows
the date box: it reads `Receipts — 2026-11-04` in the frame, in ISO form even though the box shows the
same day in your browser's own order.

**3. Search a receipt code with the search box.**

Type any part of a code — the box is labelled `Search receipt code (e.g. A1B2C3)...` and the chip inside
it says `PRESS /`. Hitting `/` anywhere on the page jumps the cursor into that box. The search matches
the code only; it does not look inside baskets, customer names or cashier names.

**4. Open a receipt by clicking anywhere on its row.**

The whole row is clickable, not just one link. In the frame the two rows are `#LR16DR` at `12:57`, basket
`ABC Relaxer (Small) +1 more`, cashier `admin`, total `GH₵ 30.00`; and `#GJPMR5` at `12:56`, basket
`Abana +1 more`, `GH₵ 132.00`. Each row also prints `NOV 4 · 2 ITEMS` under its code, and the footer
reads `Showing rows 1–2 of 2 records` with `Page 1 of 1` and two greyed arrows.

**5. Read the inspector, and reprint from it.**

The panel on the right of the frame is still showing its empty state: `Select a receipt`, `Click any row
to inspect its basket and reprint the receipt.` Once a row is clicked it becomes a card headed
`Order #LR16DR`, with `Cashier` and `Customer` side by side — a sale with no customer name recorded reads
`Walk-in Customer` — then a two-column line list headed `Item Description` and `Subtotal`, each line
showing the product name, `Qty:` and the amount charged. Below that, `Items sold` and `Total Paid`, and a
single full-width button: `Download Receipt PDF`. Chapter 09 covers that paper.

**6. Turn the pages, if the day was busy.**

The arrows at the bottom right of the list move ten receipts at a time and the label between them reads
`Page 1 of 1`. When there is only one page both arrows are dimmed and do nothing, which is the state in the
frame. Paging never resets your filters: the date, the cashier and the code you typed all travel with you.

**7. Take the day out, either as a spreadsheet or as paper.**

`Export Orders CSV` in the header downloads every receipt matching the filters on screen, not just the
page you are on. `Print Batch` next to the date box downloads an A4 sheet for the date and cashier
selected. Both are described in words below because nothing was downloaded while this manual was being
written.

## When it goes wrong

- **A cashier cannot open this screen at all, and is not told so.** They are bounced to the sign-in page
  with no message. Because the sign-in page throws away the address it was sent from, this looks exactly
  like a session that has just expired — the same page, the same blank boxes. It is the shape explained
  in chapter 01; nothing has broken.
- **`Print Batch` goes dead and says nothing about why.** It is dimmed and refuses the cursor whenever
  the date box is empty; the only hint is its hover text, `Download the day's sales PDF for the selected
  date and cashier`. Pick a date and it comes back to life.
- **Arriving from the reports screen clears your date, and takes Print Batch with it.** The eye icon on
  a report ledger row links here with the receipt code already in the search box. When a code is in that
  box the date box is deliberately left empty so the search covers all history: the list header changes
  from `Receipts — 2026-11-04` to `All Receipts`, the `View Full History` link disappears (you are
  already looking at everything), and `Print Batch` greys out until you type a date.
- **A filter that matches nothing does not fall back — it empties.** The list area shows
  `No receipts match these filters` and, under it, `Try another date, cashier, or receipt code.` The
  footer reads `No records`. The four tiles above do not change, because they are today's figures and
  never follow the filters.
- **The inspector never opens on its own.** Until a row is clicked the right-hand panel holds only
  `Select a receipt`. If you close it with the small cross in its header, it returns to that same
  message rather than keeping the last receipt on screen.
- **A cashier who reaches a receipt that is not theirs gets a not-found page, not a refusal.** Receipts
  are filtered to the cashier's own sales before they are looked up, so somebody else's receipt simply
  does not exist as far as that account is concerned. The shop has no not-found page of its own, so
  what appears is Django's — a bare 404 once debug mode is off, and on this install the debug version,
  which lists the shop's address patterns. Guessing a receipt code would never build such an address
  in any case: the code printed on the paper is not part of it. Receipts are addressed by a long
  private identifier the till hands out, so another cashier's receipt is not something you can type
  your way into.

## Notes & limits

- **This screen never changes a sale.** There is no refund, no void, no edit, no re-attribution of a
  receipt to another cashier, and no way to correct a line. Once a sale is booked it is permanent, and
  the only thing you can do to it again is print it. The hub card that links here promises "manage
  refunds or reprints"; only the reprint half is true.
- **The four tiles are always today's.** They are computed once when the page is opened and are not
  re-drawn by the filters, the search or the pager. Filtering to last Tuesday changes the list only.
  For a figure over a chosen window, use the reports screen (chapter 11).
- **What the tiles say when there is nothing to show:** `No sales recorded today yet` and a bare `—` in
  the average-order-value tile, and `Awaiting today's first sale` on the profit tile. The revenue tile
  shows `No revenue recorded yesterday` whenever yesterday had no takings at all, which is not the same
  statement as a percentage change.
- **The CSV is six columns, headed exactly:** `Receipt`, `Date`, `Time`, `Cashier`, `Items`,
  `Total (GHs)`. Note the money header is written `Total (GHs)` while the screen writes `GH₵` — same
  currency, two spellings, and the file keeps its own. Rows are one per receipt, with the full seconds in
  the time, and the file carries whatever filters are on screen at the moment you press the button. It is
  named with an `orders_` prefix and a `YYYYMMDD_HHMMSS` stamp, e.g. `orders_20261104_142530.csv`. No
  file was downloaded for this manual, so there is no picture of it.
- **`Print Batch` is a three-column A4 sheet, not the customer receipt.** It is headed `Orders by All
  Users for 4th November, 2026` (or `Orders by <username> for …` when one cashier is selected), lists
  `Order Code`, `Total Amount`, `Time Created`, and closes with a dark band reading `Total Sales:` beside
  the day's sum. The line amounts carry `GH₵`; the `Total Sales` figure is printed as a bare number with
  no currency mark and no rounding applied. The file is named with a `Sale_` prefix and the batch date as
  `DDMMYYYY`, e.g. `Sale_04112026.pdf`. No PDF was downloaded for this manual.
- **That batch total counts by day and month, ignoring the year.** The same routine behind the older
  screen adds in receipts from the same calendar day in other years. It is listed as a gap in chapter 13
  and is worth knowing before you hand a `Print Batch` sheet to an accountant.
- **There is no tender information anywhere on this screen.** The till records no payment method, so
  cash and mobile money cannot be separated here, or in any export from here.
- **The cashier dropdown lists every account, including deactivated ones**, ordered by username. A
  former cashier still filters cleanly; their old receipts remain in the book.
- **What only the other role sees, in reverse:** a cashier gets none of this. Their whole view of the
  day is the takings figure at the top of the till, labelled `Your Takings` for them and
  `Today's Takings` for the owner (chapter 08), plus their own receipts from the settlement panel.
- **The older ledger screen.** `/orders/check-orders/` is a plain, unstyled page — its own frame below —
  with `Select Date:` and `For User:` dropdowns and a single `Fetch Orders` button. Nothing in the shop
  links to it; it is reachable only by typing the address. What typing it gets you is raw markup: the
  page carries no header and no stylesheet, so the browser's own serif text on a white background is
  not a capture that went wrong — it is the screen. The navigation even has two rules that would light
  the **Orders** item on this address, but they can never fire, because this page never renders a
  navigation to light. It is written up properly in chapter 13. It is not a workflow and no part of
  this chapter depends on it.

![The legacy screen at its own address, as it stands before anything is fetched: the bold heading
"All Orders", then the label "Select Date:" beside a dropdown reading "Choose date", the label "For
User:" beside a dropdown reading "All Users", and below them one plain browser button reading "Fetch
Orders". Black text on white, top-left, in the browser's own font — no header, no navigation, no
stylesheet. There is no table, no rows, no result labels and no pager: nothing has been asked for, so
nothing has come back.](img/10-orders/10-today-legacy.png)

Related chapters: 08 (ringing the sale that puts a row here), 09 (the receipt paper), 11 (the same
receipts, totalled over a chosen window), 13 (the legacy screen and the open gaps).
