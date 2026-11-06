# myshop — setting it up on a new computer

This is the shop's till: you scan or type a product, take money, print a receipt, and it
keeps track of stock, costs, suppliers and the day's takings. It runs on one Windows
computer at the counter — not on the internet.

Everything below is the order to do things in. Plan on an hour if you are bringing your
shop history across, 20 minutes for a clean start.

---

## 1. Install four things first

| Install it because | What it is |
|---|---|
| The program itself is written in Python | **Python 3.12 or newer** — https://python.org, tick "Add to PATH" |
| Every sale, product and receipt is stored in a database | **PostgreSQL 18** — https://postgresql.org/download/windows. Pick a password for the `postgres` login and write it down |
| Bulk work (importing many products, deleting them) runs in the background | **Memurai** (a Redis server) — https://www.memurai.com. It starts as a Windows service, so you install it once and forget it |
| The barcode-style icons and the styling are rebuilt from source | **Node.js** — https://nodejs.org. Only needed when the design changes; the ready-made files are already in git |

PDF printing uses **WeasyPrint** by default. To use **wkhtmltopdf** instead, install
wkhtmltopdf (https://wkhtmltopdf.org) and set `PDF_RENDERER=wkhtmltopdf` in `.env`.
On Windows, set `WKHTMLTOPDF_PATH` to its executable if it is not on `PATH`.

## 2. Get the code

Clone the repository into a folder you will keep, e.g. `C:\shop\myshop`. If you use Git
for Windows, right-click the folder → *Git Bash here* and run:

```
git clone <your repository address> myshop
cd myshop
```

## 3. Two folders that are NOT in git — you must bring these yourself

Git deliberately does not store them, so a fresh clone is missing them:

- **`.env`** — the private settings: the database password, the secret key, your shop name,
  address, phone and the line printed at the bottom of receipts.
- **`media\`** — the product photos.

Copy `media\` across from the old computer as it is. For `.env`, make a new empty file
called `.env` inside the project folder and put these lines in it, with your own values:

```
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=copy-a-long-random-string-here
POSTGRES_DB=myshopproject
POSTGRES_USER=postgres
POSTGRES_PASSWORD=the-password-you-chose-in-step-1
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
CELERY_BROKER_URL=redis://127.0.0.1:6379
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379
COMPANY_NAME=Noble Cosmetics Ltd.
COMPANY_LOCATION=your shop location
COMPANY_PHONE=+233 ...
COMPANY_EMAIL=
COMPANY_FOOTER=Goods sold are not returnable. Thank you for your patronage!
PDF_RENDERER=weasyprint
# Optional when PDF_RENDERER=wkhtmltopdf and wkhtmltopdf is not on PATH:
# WKHTMLTOPDF_PATH=C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe
```

Without `POSTGRES_PASSWORD` the app fails with a confusing database error, so do this
before anything else. Keep `.env` out of git — it is already ignored for you.

## 4. Give the project its own Python

Install the free tool **uv** (`winget install uv`, or the installer from
https://docs.astral.sh/uv/), open PowerShell in the project folder, and run:

```
uv sync
```

That reads `pyproject.toml` and `uv.lock`, creates a folder called `.venv`, and installs
every package the shop needs at the exact versions this project was built with. There is no
other list of packages in this project, so don't try to install them one at a time by hand —
you will miss some.

The folder must be named exactly `.venv`. The start-up scripts look for
`.venv\Scripts\python.exe`, and a differently named folder means nothing happens when you
sign in, with no error message.

## 5. Get your shop's history onto the new machine

Do this if the old computer has products, prices, stock and past sales you want to keep.

On the **old** computer, in PowerShell:

```
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -d myshopproject -f C:\shop-history.dump
```
Type the database password, then copy `C:\shop-history.dump` and the `media\` folder to a
USB stick.

On the **new** computer:

```
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE myshopproject;"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d myshopproject -f C:\shop-history.dump
```

If you installed a different PostgreSQL version, the `18` in those paths is that version
number instead (for example `PostgreSQL\17\bin`).

## 6. Or start with an empty shop

Skip step 5 and build the (empty) tables:

```
.venv\Scripts\python.exe manage.py migrate
```

Then make your own login (step 7), sign in, and add products from a spreadsheet on the
website at **http://127.0.0.1:8000/products/import-products/**. That import runs in the
background, so the two services from step 8 have to be running — otherwise the progress bar
just sits at 0%.

There is a command-line version of the same import
(`.venv\Scripts\python.exe manage.py load_csv products.csv --actor-id <your account id> --request-key <a fresh uuid>`),
and it needs both of those options: the id of an ADMIN account that already exists, and a
once-only reference number so a retry cannot double-book stock. The website does all of that
for you, so use the website unless you have a reason not to.

## 7. Make your own login

The first account is created from the command line; after that you add cashiers inside the
website (Accounts page).

```
.venv\Scripts\python.exe manage.py createsuperuser
```

It asks for a username, then a password twice. A new account like this is an ADMIN, which
sees everything — stock, costs, profit and reports.

## 8. Try it, then make it start by itself

Run the shop once by hand to be sure everything is wired up:

```
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000 in your browser, log in, scan something. Close it with
`Ctrl+C` in that window.

To start both services now, run this from the project folder:

```
scripts\services\start-both.cmd
```

The launchers run in the background without visible PowerShell windows; their output and
errors go to the log files in step 9. To start them automatically each time you sign in,
choose **one** of these methods:

### Startup-folder shortcut (simplest)

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\services\install-startup.ps1
```

This installs one shortcut in your Windows Startup folder. Remove it with:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\services\install-startup.ps1 -Remove
```

### Task Scheduler

Alternatively, register two hidden, per-user scheduled tasks:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\services\register-tasks.ps1
```

This runs as the current signed-in user and does not require an elevated PowerShell. Remove
the tasks from PowerShell with:

```
Unregister-ScheduledTask -TaskName myshop-devserver,myshop-celery-worker -Confirm:$false
```

Both installers check for `.env` and the project virtual environment before installing. At
sign-in, the launchers wait up to five minutes for PostgreSQL and Redis to accept connections,
using the hosts and ports in `.env`; a timeout or missing setup is recorded in `launcher.log`.
Keep the project folder in its final location before installing. If you move it, remove and
reinstall the shortcut or scheduled tasks so they point to the new location. Do not install
both startup methods, since both would try to launch the same services.

## 9. How to tell it is working

- Open http://127.0.0.1:8000 — the login page means the website is up.
- Import a small spreadsheet at **http://127.0.0.1:8000/products/import-products/**: the
  progress should move off 0%. That proves the background worker is alive.
- Every note is in `C:\Users\<you>\AppData\Local\myshop\services\logs`:
  - `launcher.log` — what the start-up decided each time ("started", "skip: port 8000
    already held by pid 1234"). Read this first when something did not come up.
  - `devserver-<date>.log` — the website's own output and errors.
  - `celery-worker-<date>.log` — the background worker's output. A healthy start ends with
    `celery@kb ready.`

## 10. After you change the code later

```
git pull
.venv\Scripts\python.exe manage.py migrate
```

If the update mentions icons or styling, also run `npm install` once and then `npm run
build`. Then sign out of Windows and sign back in to restart the services. If you have not
installed either automatic startup method, run `scripts\services\start-both.cmd` from the
project folder instead; it does not start duplicate instances.

## 11. Keep your shop safe

Back up the database every night you trade — one command, and copy the file somewhere other
than this computer (a USB stick you leave plugged in is not a backup):

```
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -d myshopproject -f C:\backups\shop-<today>.dump
```

Also copy the `media\` folder when you add product photos, and keep a spare printed copy of
`.env` somewhere safe — without that password the data cannot be opened.

## 12. When it misbehaves

| What you see | What it usually means | What to do |
|---|---|---|
| Browser says "can't reach this page" | The website is not running | Sign out and back in, or double-click the Startup shortcut; check `launcher.log` |
| Import stays at 0% | The background worker is not running | Same as above; `celery-worker-<date>.log` should end in `celery@kb ready.` |
| A message about the database or password | `.env` is missing or wrong | Fix `POSTGRES_PASSWORD`, then restart |
| "column ... does not exist" or a page breaks after an update | The tables are behind the code | Run `manage.py migrate` |
| Icons or colours missing after you change them | The design files were not rebuilt | `npm install` then `npm run build` |
| Two of something running at once | Started by hand as well as automatically | Harmless — the start-up scripts refuse to stack; but don't run `runserver` twice yourself |
| Need to find a product for sale | Barcode scanners are not integrated | Open the register and use its product search |

## 13. Things worth knowing

- `runserver` is the development server. It is fine for one computer at the counter and it
  is what the shop uses today. Do not point the public internet at it.
- None of the service setup scripts needs an administrator prompt.
- If the computer reboots while you are trading, you lose nothing that was already saved —
  but sign back in before the next customer, because the till only comes back after you do.
