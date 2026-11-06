# Onboarding manual

Thirteen short chapters that teach the shop the way a new person actually learns it: one screen at a
time, in the order the work happens. Every screenshot was taken from the running system with its real
data, so the product names, prices and counts you see are the ones the shop is working with today.

Start at chapter 01 and read forward. Each chapter has the same five blocks — what the screen is for,
what you need before you open it, the steps, what goes wrong, and what the screen will never do — so
once you have learned the shape of one you have learned all of them.

## The two tracks

| You are | Read |
|---|---|
| the owner | 01 → 13, in order |
| a cashier | 01, 02, 08, 09, then 10 if you check your own day |

## Chapters

| # | Chapter | What you end up able to do |
|---|---|---|
| 01 | [Sign in, and your own account](01-sign-in.md) | get in, change your password, spot a dead session |
| 02 | [The owner's hub](02-owners-hub.md) | reach every workflow from one screen, on a laptop or a phone |
| 03 | [Bring the catalogue in](03-bring-the-catalogue-in.md) | load a CSV, add one product |
| 04 | [Read the Products & Stock ledger](04-read-the-ledger.md) | find a product, read the valuation tiles, use the filters |
| 05 | [Receive a delivery](05-receive-a-delivery.md) | book a supplier delivery against open batches |
| 06 | [Count and correct stock](06-count-and-correct-stock.md) | reconcile a shelf count without fiddling the numbers |
| 07 | [Remove products](07-remove-products.md) | delete a line, and know why some lines refuse |
| 08 | [Work the till](08-work-the-till.md) | ring a sale as a cashier, on the counter or on a phone |
| 09 | [Print a customer receipt](09-print-a-customer-receipt.md) | hand someone a receipt and reprint one later |
| 10 | [The orders and receipts ledger](10-orders-and-receipts-ledger.md) | find any sale the shop has made |
| 11 | [Sales reports and exports](11-sales-reports-and-exports.md) | read the day, the week, the cashier; take it to a spreadsheet |
| 12 | [Accounts and roles](12-accounts-and-roles.md) | add a salesperson, reset a password, deactivate a login |
| 13 | [Known gaps and upkeep](13-known-gaps-and-upkeep.md) | what the shop does not have, and how to keep this manual true |

## What is not photographed

The screenshots were taken **without writing to the shop's books**. That is a deliberate limit, and it
means a handful of outcomes are described in words rather than shown: a completed import, a booked
delivery, an applied stock correction, a rung-up sale, a printed receipt, an export file, and the
out-of-balance state that only exists once data is forced out of shape. Where a chapter
stops at a button, it says so. Nothing in here claims a frame shows something it does not.

## Re-shooting the pictures

The images live in `img/<chapter>/` and are produced by one script. The server keeps its window busy,
so open two:

```
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Then, in a second window:

```
set TUTORIAL_SHOOT_PASSWORD=<the tutorial accounts' password>
.venv\Scripts\python.exe scripts\tutorial\shoot_live.py
```

Two rules the script depends on:

- **Do not add `--nothreading`.** The register and the ledger load their tables with htmx, and a
  single-threaded server deadlocks on the second request, which is what makes a capture hang forever.
- The script signs in as `tutorial` (owner) and `tutorialpos` (cashier) and clicks nothing that writes.
  Those two accounts exist only for this; make them with:

  ```
  .venv\Scripts\python.exe manage.py shell -c "from authapp.models import Account;from django.contrib.auth.hashers import make_password;import os;p=os.environ['TUTORIAL_SHOOT_PASSWORD'];[Account.objects.update_or_create(username=n,defaults={'password':make_password(p),'is_staff':t=='ADMIN','is_superuser':t=='ADMIN','user_type':t}) for n,t in [('tutorial','ADMIN'),('tutorialpos','SALEPERSON')]]"
  ```

  and delete them with `.venv\Scripts\python.exe manage.py shell -c "from authapp.models import Account; Account.objects.filter(username__in=['tutorial','tutorialpos']).delete()"`.

If the UI changes, re-run the script before you trust a chapter's caption — and if a caption now
describes something the frame no longer shows, fix the caption, not the claim.
