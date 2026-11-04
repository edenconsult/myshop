# 13. Known gaps and upkeep

## What this is for

This chapter is the list the owner keeps beside the till: what the shop does not actually do, what its
own labels promise, and what to look at when a screen goes quiet. Read it once so nothing surprises you
later, and come back to it whenever a chapter's picture and the real screen stop agreeing.

## You need

- **Who can read it:** whoever keeps the shop running. Two of the items below need the owner account;
  the two commands need someone standing at the shop computer with access to its project folder.
- **Where it lives:** in the other twelve chapters. This chapter has no screen of its own — it is a
  checklist about their screens, plus one retired screen that step 4 photographs. That screen is the
  curiosity, and you can only reach it by typing its address.
- **What must already exist:** for the commands, a running install and a spreadsheet; for the log
  reading, the shop's own start-up having been installed the way the setup notes describe.

## Steps

### 1. Read the promises against what the code actually does

| The screen says | The shop does |
|---|---|
| `Fast Barcode Lookup` on the hub's till card, and "scan barcodes" in the same card's sentence | No barcode scanner is integrated anywhere. The built-in help says it plainly: `Barcode scanners are not integrated; use the on-screen product search.` |
| `accept Cash, MoMo, or Card payments without delay` | A sale records an amount and nothing else. There is no tender field, so a cash sale and a mobile-money sale are indistinguishable in every later report. |
| `manage refunds or reprints` | Reprints exist. Refunds do not: a booked sale cannot be edited, reduced or voided from any screen. |
| `Instant Receipts` | The receipt link appears under the sale it belongs to, and only after the sale books. |
| `Download CSV` on the hub's reports card | It navigates to the reports screen. It downloads nothing. The real export is a button on that screen. |
| `Live update` beside the snapshot tiles | The hub is a single read of the moment it was opened. Nothing refreshes it while you watch. |
| `Ready for Checkout` | A fixed label on a card, not a status the shop measures. |
| `GH₵` everywhere else | The till's own success banner writes the same money as `GHs`: `Order Number … totaling GHs … was successful. Thank you.` The legacy screen in step 4 also writes `GHs`, and the printed receipt's total line writes `(GHS)`. None of the three is corrected anywhere. |
| `Your username and role are handled by an administrator.` | True, and there is no way to change either yourself. |
| `Up to 10 digits.` under the profile phone box | Length is capped at ten characters; nothing checks that they are digits. |

### 2. Know the features that have no screen at all

Not "hidden" — absent. Do not spend time hunting for these.

- **Self-service password reset.** No link on the sign-in card, no route behind it, and the shop sends
  no email of any kind. The owner resets a password on the accounts screen, in person.
- **Barcode scanner integration.**
- **Refunds or voids of a booked order.** The correction route is a fresh sale plus a note on paper.
- **An active/inactive switch for a product.** A product line is either removed or taken to zero stock;
  there is no "hide it from the till but keep it" state. Switching a person off is a different thing and
  does exist, on the accounts screen.
- **Tender type and change due.**
- **The price-change trail.** When a delivery applies a new selling price, the shop stores the old price
  and the new one, but no screen shows either. The delivery detail page has no price-change column.
- **Category and supplier screens.** Category is a fixed five-choice list inside the product dialog;
  supplier is free text typed onto a delivery. There is nothing to open, so nothing to photograph.
- **A browser print dialog.** Every "Print" control in the shop hands you a downloaded file instead.
- **A preview of your rows, and a mapper you can aim yourself.** The import dialog is not blind: it reads
  your first line, lists the six columns it knows, counts how many of them your file carries, names the
  required ones that are missing, and keeps the Import button pale until the schema passes — chapter 03
  step 2 walks through that panel. What no screen does is show you a single row of data before you press
  the button, or let you tell the shop that a column named something else is the quantity column. The
  header match is letter-for-letter, so the fix lives in the spreadsheet, not in the dialog.
- **A low-stock alert of any kind.** The restock tiles and filters are the alert; nothing reaches out to
  you.

### 3. Learn the dead ends and the duplicated links

- The hub's `Find Receipt` and `View All Orders` are the same destination twice.
- The hub's `Download CSV` and `View Daily Report` are the same destination twice.
- The hub's `See All Receipts in Orders` and `Open Full Ledger` are the same destination twice.
- The receipt numbers in the hub's recent-transactions table are links, but they open the orders ledger
  rather than the sale they name.
- The help icon is a blank square in the header, in the phone drawer and on the hub card. The glyph is
  missing from the shop's icon set; the link behind it works.
- The legacy screen in step 4 is wired end to end and linked from nowhere.
- One print address spells its own segment differently from its neighbours, so a hand-typed address that
  looks right will not match. Nothing on screen shows you the difference.
- The help page is gated like every other page: opened by a browser with no session it shows the
  sign-in card, which is exactly what the frame in chapter 02 records.

### 4. Look at the legacy screen once, so it never frightens you

![An unstyled page on a plain white background: no shop header, no colour, no layout. A bold serif
heading reads "All Orders". Under it three plain browser controls stacked one per line — "Select Date:"
with a dropdown showing "Choose date", then "For User:" with a dropdown showing "All Users", then a grey
browser button reading "Fetch Orders". The rest of the page is empty.](img/10-orders/10-today-legacy.png)

- **How to reach it:** type its address into the browser. No button in the shop leads here, and it is
  owner-only: a cashier who types it is bounced back to their own register and never sees this page.
- **What it is:** the shop's first day-list, kept alive after the ledger replaced it. It does still
  work: pick a date and press `Fetch Orders` and a panel fills underneath with a table headed
  `Orders — [the date]`, columns `S/No.`, `Order Code`, `Total Amount`, `Time Created`, a line reading
  `Total Sales: GHs …`, and a `Download Report` button that hands over a day-batch file. With no sale
  that day it says `NO ORDERS MADE BY … ON THIS DATE …`.
- **Why it looks like that:** it is the only screen in the shop that never got the restyled shell, so it
  has no header, no theme, and plain browser controls.
- **The bug to know about:** its date filter matches the day and the month but ignores the year. Choose
  a date and the list can pull in the same calendar day from an earlier year, and the `Total Sales`
  figure adds them together. The number can be quietly too big. Nothing on the screen warns you.
- **What to do about it:** nothing. Use the orders ledger in chapter 10, which filters properly. This
  screen exists because nobody has deleted it yet.

### 5. Treat the shop's own admin area as a last resort

The admin area is a raw table viewer that ships with the software the shop is built on, and it is
switched on here: the address is the shop's own, with `admin/` on the end. The setup notes never mention
it, and nothing in this manual depends on it. It asks for a staff login on a page of its own, not the
shop's sign-in card, and it lists the shop's tables as the database stores them — including the per-sale
batch allocations that no shop screen ever shows. The batch rows themselves *are* on a shop screen: the
**Batch History** dialog of chapter 06, which is what that chapter's batches frame photographs.

What it cannot do is move the books. A product's stock figure is read-only there, and products cannot be
added or deleted at all. The sale, sale-line, delivery, batch, allocation, adjustment and import-log
tables are registered so that they can be read and nothing else — no adding, no editing, no deleting. So
this door is not a way to put the shop out of balance. That state does exist, but it comes from a write
that died part-way, or from work done straight on the database with the tools the setup notes use for the
restore; the way back is chapter 06's **Sum of batches · shelf count** line and the reconciliation check
in step 6.

What it *can* change is the two things the shop's own screens police: a product's name, prices, category
and photo, and the account rows — who is active, who counts as an owner, and the stored password, which
there is a plain box for. That is the real risk here, and the reason this chapter keeps calling the admin
area a history viewer and a developer's break-glass rather than a workflow: it lets you change a person's
access while skipping every rule the accounts screen in chapter 12 puts up.

### 6. Run the two commands a technician uses

Neither has a screen; both are typed at a prompt in the shop's project folder. The setup notes write out
one of them — the loader — and never mention the reconciliation check at all, so its exact wording comes
from whoever set the shop up. The check is the simpler of the two: it takes no arguments, just the run.

- **The inventory reconciliation check.** Read-only. It answers one question — are the shelf numbers,
  the batch numbers and the sale costs still consistent with each other — and never changes anything.
  A clean run ends with `Inventory reconciliation passed.` A failing run prints one line per kind of
  problem with a count and a few record references, then stops with
  `Inventory reconciliation failed with … issue(s).` Run it after any power cut, any crash, and any
  time a total looks impossible. It is the check to run before you phone for help.
- **The spreadsheet loader.** The command-line version of the import in chapter 03, for a file too large
  or too awkward to upload. It needs three things: the file, the identity of an active owner account, and
  a reference number for the run. That number is what makes a retry safe: send the same file under the
  same number again and the shop hands back the run it already did and writes nothing twice; send
  *different* data under that number and it refuses with `This request key was already used for different
  data.` A new number is a new run, and a new run of a file the shop has already eaten is judged from
  scratch — its rows now collide with products that exist. The setup notes tell you to invent a fresh
  number when you *start*, which is the sentence people read backwards. The loader also has a switch to
  update the details of products that already exist without touching their stock. It answers
  `Catalogue import … completed.` when it gets through, and refuses with a plain reason — file not found,
  or an account and reference that do not fit — before it writes anything.

### 7. Recognise a background service that is not running

The tell is one screen: an import that opens its dialog, shows `Importing Products`, and sits at zero
percent forever while the button reads `Stop watching`. The dialog keeps asking the shop whether the job
has moved, and the job has never started, because the worker that runs it is down. The import itself is
not broken and your file is not lost.

- Closing the dialog is honest about one thing: `Closing this dialog does not stop the import — the
  worker keeps running and the table refreshes when it is done.` That is exactly the assumption that
  fails when the worker is down.
- The same silence covers removals, which are handed to the same service.
- The fix is not in the shop's screens. Restart the services the way the setup notes describe, then
  start the import again.

### 8. Know where the notes are and how to keep the data

- **The log folder** is in your own user profile on the shop computer, under a folder named for the
  shop and a subfolder for its services. Three kinds of file live there:
  - the launcher note, which records what start-up decided each time it ran — including the useful
    refusals, like a port already held by something else;
  - a website note for each day, holding the shop's own output and errors;
  - a worker note for each day. A worker that came up properly ends its opening with a `ready` line, so
    that file is where you prove the service behind imports is alive.
- **The nightly copy.** Once for every trading day, take the database dump the setup notes give, and put
  the file somewhere that is not this computer. A stick left in the same machine is not a backup. Copy
  the pictures folder whenever you add product photos, and keep a printed copy of the shop's settings
  file — without that password the data cannot be opened again.
- **If the machine restarts while you are trading:** nothing already saved is lost, but the till only
  comes back after someone signs into Windows again.

### 9. Re-shoot this manual when a screen moves

The pictures are produced by one script that signs in and photographs the shop without pressing any
button that writes to the books. Its address, its two rules and the accounts it needs are on the front
page of this manual, not here. What matters for upkeep:

- If a screen changes, re-shoot the affected chapter in the same change, not a month later.
- If a caption no longer matches the frame, fix the caption. Do not fix the shop to match the manual.
- The index page of this manual also lists what is deliberately not photographed, so a chapter stopping
  at a button is a stated limit rather than a missing picture.

## When it goes wrong

- **A refusal and an expired session are two different pictures, and telling them apart is the whole
  skill.** A screen meant for the other seat, typed by someone who *is* signed in, never shows the
  sign-in card: the shop carries you back to your own opening page — the register for a salesperson, the
  hub for the owner — and says nothing about why. Only a dead session shows the card, and the card does
  not tell you which happened or where you were going, because the shop forgets the destination: sign in
  from it and you still land on your opening page. So read the page you arrive on. Back at your own till,
  the screen you typed was never meant for your role — ask the owner. Shown the card, sign in again and
  try once.
- **A login card inside a half-finished screen** is a dead session, not a refusal: the page stayed open
  while the session ran out, and the panel's next request came back asking to sign in, so the card was
  pasted into the panel. Sign in and the panel loads. A refusal, by contrast, is a whole-page trip back
  to your own opening page.
- **The legacy screen's total is larger than the day.** That is the year blend in step 4, not a
  calculation error in the reports. Re-run the day on the orders ledger.
- **An import at zero forever** is the down worker in step 7, not a rejected file. A rejected file is
  refused on the spot with a sentence about the file.
- **A page that breaks straight after an update** — a complaint about a missing column, or a screen that
  used to work now throwing at you — means the database tables are behind the code. That is a migrate,
  and it is in the setup notes.
- **Missing icons or colours after a change** means the design files were not rebuilt. Nothing in the
  shop's own screens can fix that.
- **Two of something running at once** is harmless: the start-up scripts refuse to stack. But do not
  start a second copy by hand, because that one will not refuse.

## Notes & limits

- **This chapter fixes nothing.** Every item above is a gap for the owner to decide about, and each
  decision deserves its own change to the shop, not an edit here.
- **The shop's labels are the least trustworthy part of the shop.** Where a card and a chapter disagree,
  believe the chapter, and believe the screen in front of you over both.
- **Money is written three ways**, the same three chapter 08 counts: `GH₵` on the screens you work,
  `GHs` in the till's success banner and on the legacy screen, and `(GHS)` on the printed receipt's
  total line. All three are the same currency; the manual quotes each exactly as its screen writes it.
- **Nothing here is versioned.** The manual describes the shop as it runs today. If the shop has been
  updated since a chapter was written, that chapter is the first thing to re-check.
- **What only the owner can see, still cannot be seen by anyone:** the price-change trail, tender types,
  refunds. These are not hidden behind a role — they do not exist on any screen at all.
- **This manual never shows a screen that does not exist**, and never shows a screen as doing something
  it has not been seen to do. Where a step stops at a button, that is the limit of what was photographed.

Related chapters: 01 (the sign-in card a dead session leads to, and the one a refusal never shows), 02
(the hub's mislabelled cards), 03 (the import and its progress dialog), 04 and 10 (the ledgers that
replaced the legacy screen), 08 (the till a bounced cashier is handed back to), 11 (the reports whose
exports the hub only pretends to do), 12 (accounts, where a password is actually reset).
