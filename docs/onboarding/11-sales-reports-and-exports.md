# 11 — Sales reports and exports

## What this is for

This is the screen that answers "how did we do". It takes a stretch of days — today, yesterday, the last
week, the month so far, or any pair of dates you type — and tells you what was sold, what it cost the shop
to buy that stock, and what is left over as profit, split by cashier and by product department. When you
need the same figures outside the shop, it hands them to you as a spreadsheet file or as a printed report.

## You need

- **The owner seat (ADMIN).** The reports screen is gated to the owner. A cashier sent here lands back on
  the sign-in page with no explanation, which looks the same as an expired session (chapter 01).
- **The screen: the Sales Reports tab.** Open it from the top navigation item **Sales Reports**, from the
  hub's *Sales & Revenue Reports* card via **View Daily Report**, or from the `Sales Reports` button on
  the orders ledger.
- **Data that must already exist:** booked sales inside the window you pick. The figures are built from
  the receipts themselves and from the cost frozen onto each line at the moment it was sold — nothing here
  is entered by hand, and nothing here re-prices history.
- The transaction ledger at the bottom pages at **10 receipts**. The tiles and panels above it do not
  page; they always describe the whole window.

## Steps

One frame covers this chapter. Everything below happens inside it, and the whole body of the screen is
re-drawn each time you change a filter.

![The Sales Reports tab: a title with a date pill, three buttons in the header, a filter bar with four
preset buttons, two date boxes joined by "to", a cashier dropdown and a Fetch Report button; then four
KPI tiles, two breakdown panels side by side, and a nine-column transaction ledger with two rows.](img/11-reports/11-reports.png)

**1. Pick a window with one of the four preset buttons.**

They read `Today`, `Yesterday`, `Last 7 Days` and `MTD: Nov 2026` — the last one is named for the current
month, so it says something different every month. The chosen button fills solid green. The pill beside
the page title then states the window the numbers cover; in the frame it reads `NOV 4, 2026`, and for a
multi-day window it reads the two ends joined by a dash.

**2. Or type your own window in the two date boxes.**

Change either box and the screen treats the window as custom: the preset buttons all drop back to plain
text and the pill, the tiles, the panels and the ledger all recompute. Press `Fetch Report` at any time to
re-pull the same window.

**3. Narrow to one cashier with the dropdown.**

It reads `All Cashiers` in the frame and lists every account. Choosing one narrows the whole screen —
tiles, panels, ledger and both exports — to that person's receipts.

**4. Read the four tiles, and read the small line under each.**

In the frame: `PRODUCTS SOLD 12` over `Units rung up in the window`, with `No prior period to compare` on
the left and `2 receipts` on the right; `GROSS REVENUE GH₵ 162.00` over `What the receipts charged`, with
`GH₵ 81.00 avg per receipt`; `COST OUTLAY GH₵ 121.05` over `Catalogue cost of those units`, with
`74.7% of revenue` and `0.34× on cost`; and `REALIZED PROFIT GH₵ 40.95` over `Revenue less cost outlay`,
on a card whose figure, icon and margin note are green, with `25.3% margin`. When there *is* a previous
window of the same length to compare with, that left-hand line becomes a percentage against it —
`… % vs previous 7 days`, green with an up arrow or rose with a down arrow.

**5. Look at the two breakdown panels.**

`Sales by Cashier`, subtitled `Who rang up the receipts in this window`, carries a badge counting the
registers — `1 REGISTER` in the frame — a solid share bar, one line per person with the first two letters
of their name in a circle, their receipts and their share of revenue (`2 RECEIPTS · 100.0% OF REVENUE`, `GH₵ 162.00`), and a
footer line `REVENUE AUDITED GH₵ 162.00` that repeats the tile figure so you can see the split adds up.
`Sales by Department`, subtitled `Line value grouped by product category`, badges how many departments
sold (`2 ACTIVES`), shows one card per department with its share, units and value — `Skincare 87.7%`,
`10 units`, `GH₵ 142.00` and `Haircare 12.3%`, `2 units`, `GH₵ 20.00` — and closes with
`BEST SELLER BY UNITS`, which in the frame is `Abana`, marked `NO SKU`, at `6 units` for `GH₵ 72.00`.

**6. Read the transaction ledger, and check a single receipt from it.**

It is headed `Transaction Ledger` with `Every receipt in the window, with its cost outlay and realized
profit`. The columns are `S/No`, `Receipt`, `Cashier`, `Items & SKU`, `Qty`, `Cost Outlay`,
`Selling Total`, `Realized Profit`, `Actions`. The two rows in the frame are `01  #LR16DR`, `admin`,
`ABC Relaxer (Small)` over `NO SKU +1 LINE`, `3`, `GH₵ 21.00`, `GH₵ 30.00`, `+GH₵ 9.00`; and
`02  #GJPMR5`, `9`, `GH₵ 100.05`, `GH₵ 132.00`, `+GH₵ 31.95`. Positive profit is written with a plus sign
and in green.

**7. Use the two icons in the Actions column.**

The eye opens that receipt in the orders ledger (chapter 10) with its code already in the search box. The
printer downloads the customer receipt itself (chapter 09). They are quiet grey icons with no labels;
hovering explains each one.

**8. Filter the ledger to one code, if you are hunting.**

The box at the top right of the panel reads `Filter by receipt code…`. Type and press Enter. This filter
applies to the ledger only — the tiles and panels above keep describing the whole window.

**9. Take it out as a spreadsheet or as paper.**

`Export CSV` and `Download PDF Report` in the header both hand you a file for the current window, cashier
filter and ledger filter. Both are described in words under Notes & limits; neither was downloaded while
this manual was being written, so there is no picture of either.

## When it goes wrong

- **A reversed date range is silently swapped, never refused.** Type a start later than the end and the
  screen quietly re-reads them the other way round: the tiles, the panels and the ledger all show the
  sensible window, and no message appears. Nothing tells you that you typed it backwards — except the
  pill beside the title, which is built from the two boxes as they stand and so keeps showing them the
  way you typed them.
- **A custom range you cannot read falls back in the numbers only.** If either date box is empty or
  holds something the screen cannot parse, the window behind the figures becomes today alone: the tiles,
  the panels and the ledger all redraw for today. The filter bar does not follow. No preset button
  lights — the window is still marked custom — the boxes stay exactly as they are, and the pill
  beside the title reads `Invalid Date`. There is no error band anywhere. Reload the page and the bar
  snaps back too, with `Today` lit and both boxes set to today.
- **An empty window says so, plainly.** The body opens with `No sales in this range` and, under it,
  `Nothing was rung up … on <date>.` or `Nothing was rung up … between <start> and <end>.` followed by
  `Pick another window or clear the cashier filter.` The tiles still draw, at zero.
- **The panels have their own empties.** `No receipts to attribute in this range.` in the cashier panel,
  and `No product lines sold in this range.` in the department panel. The ledger answers with
  `No receipts in this window` and either `Try another date or cashier.` or, when a code filter is
  running, `Nothing matches "<code>". Clear the filter or widen the date range.` Its footer reads
  `No receipts`.
- **A tile with nothing to compare against does not show zero.** It shows `No prior period to compare` in
  grey. That is a different statement from "down 100%", and it is what you will see on the first day of
  trading or on any window whose previous stretch was empty.
- **A receipt that sold below its cost turns rose.** The `Realized Profit` cell drops its plus sign and is
  drawn in rose instead of green — a line sold under what the shop paid for it shows as a negative figure
  in the colour of a loss. Both rows in the frame are positive, so this picture does not show it; the
  styling is the only warning the screen gives, and there is no message beside it.
- **A ledger filter does not travel the way most people expect.** Type a code, then press
  `Export CSV` or `Download PDF Report`: the file's line list is filtered. The PDF keeps its
  `Overall Summary` figures for the whole window above that filtered ledger, so the totals and the rows
  disagree. The CSV carries no totals at all — one header row and one row per receipt — so only its row
  list is affected. If you want the PDF's totals to match its rows, clear the filter first.
- **A cashier cannot see any of this**, and is not told why — the bounce to the sign-in page is the same
  one described in chapter 10.

## Notes & limits

- **This screen will never tell you about cash versus mobile money.** There is no tender split, because
  the till does not record a payment method at all. What used to be a payment breakdown on paper mockups
  is now the cashier breakdown, and it answers a different question.
- **It will not correct a past window.** Costs are frozen onto each line when the sale is booked. A stock
  correction or a restock at a new price afterwards changes future reports and the stock valuation, never
  a report that has already been read.
- **The screen combines cost that the export splits.** `Cost Outlay` and `Realized Profit` on this screen
  are one figure per line whether the cost behind it was known at sale time or estimated. The CSV keeps
  them apart, which is the honest version — see below.
- **The CSV is twelve columns, headed exactly:** `S/No`, `Receipt`, `Date`, `Time`, `Cashier`, `Units`,
  `Actual Cost`, `Estimated Cost`, `Revenue`, `Actual Profit`, `Estimated Profit`, `Estimated Lines`. The
  last column counts how many lines in that receipt were costed from an estimate rather than a booked
  batch cost, so an accountant can see how much of the profit figure is soft. Money is written as plain
  numbers with no currency mark anywhere in the file, and the date and time are the shop's own clock. The
  filename starts `sales_report_`, then the window's start date, then a `YYYYMMDD_HHMMSS` stamp that
  itself begins with the same date again — for example
  `sales_report_20261104_20261104_142530.csv`. The date is not a typo: it really is printed twice. No
  file was downloaded for this manual.
- **The PDF is A4 and mirrors the screen, not the CSV.** It opens with the shop header, then
  `Sales & Revenue Report — All Cashiers` (or one cashier's name), the window spelled out with a day
  count, an `Overall Summary` table, then `Sales by Cashier`, `Sales by Department` with the best seller
  under it, and a `Transaction Ledger` whose heading carries the row count. Its summary money is written
  `GH₵`, but the ledger's `Cost`, `Total` and `Profit` columns are bare numbers with no currency mark, and
  the closing line reads `Totals — cost … revenue … profit …`. The filename starts `Reports_` with a
  `DDMMYYYYHHMMSS` stamp, e.g. `Reports_04112026142530.pdf`. No PDF was downloaded for this manual.
- **"Print" means a file arrives, not a page appears.** There is no browser print dialog anywhere in this
  shop; both buttons hand a download to your browser.
- **The hub card that leads here is labelled `Download CSV` and downloads nothing** — it navigates to this
  screen. The real export is the `Export CSV` button in this screen's header.
- **Currency is spelled three different ways across the shop and none of them is wrong.** `GH₵` on this
  screen and on the till, `Total (GHs)` as the orders ledger's CSV column header, `TOTAL (GHS)` on the
  customer receipt. They are quoted as the shop writes them throughout this manual and are not corrected.
- **The wording is not perfectly consistent either.** The subtitle under the title says "realised profit"
  while the tile and the ledger column say `Realized Profit`. Both are on the same screen at the same
  time; neither is a different figure.
- **Percentages are rounded to one decimal and shares are of revenue**, so a department list can add up to
  99.9% or 100.1%. The money columns, not the percentages, are what reconciles.
- **What only the other role can see:** nothing here is visible to a cashier. Their only figure is the
  takings chip at the top of the till, which reads `Your Takings` for them and `Today's Takings` for the
  owner (chapter 08) — the same gross revenue, narrowed to one person, with no cost and no profit attached.

Related chapters: 10 (the receipt behind every row), 08 (what makes a row appear), 09 (the customer
paper), 13 (the gaps this screen still leaves open).
