# Onboarding Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a committed harness that photographs every screen this POS can show, and publish thirteen numbered Markdown chapters in `docs/onboarding/` that a new owner or cashier can follow from the login form to a printed receipt.

**Architecture:** A disposable second install — database `myshop_tutorial`, port `:8010`, Redis index 15, Celery queue `tutorial` — is reached only through a settings shim in this lane, so no demo write can ever land in the shop's books. `seed_demo.py` builds each screen's state by calling the real inventory and checkout services; `shoot.py` replays a JSON manifest through Playwright with two cookie jars (owner and cashier) and writes PNGs plus a `SHOTLOG.md`; `verify.py` runs four gates that prove nothing was skipped and nothing rotted. The chapters are prose around those images, and every claim in them is re-verified against the tree before it is written.

**Tech Stack:** Django 6.1, PostgreSQL (psycopg2), Celery + django-celery-progress over Redis, WeasyPrint, Playwright for Python (sync API, Chromium), htmx + Alpine.js under test, PowerShell 5.1 launchers, `uv` for dependencies.

**Spec:** [docs/superpowers/specs/2026-11-03-onboarding-tutorial-design.md](file:///C:/RebuildEden/django/myshop/docs/superpowers/specs/2026-11-03-onboarding-tutorial-design.md) — read it with this plan. Its "Verified current state", "Ground rules for honest documentation" and "Route coverage matrix" sections are requirements, not background. Where this plan and the spec disagree, the spec is wrong: fix the spec in the same commit and say so.

## Global Constraints

- Chapters are exactly the thirteen filenames in the spec's "Deliverable layout", numbered `01`–`13`, no additions, no merges.
- Every app route must appear in the spec's route-to-chapter matrix, and every matrix row must be a real route. As of 2026-11-04 the working tree resolves to **54** routes (11 `authapp`, 43 `core`) listed as **59** matrix entries; committed `HEAD` is 53, because the other lane has `/help/` and four extra `receipts/` routes sitting uncommitted in this tree. The gate therefore reads the count from the spec's "Verified current state" bullet instead of hard-coding it — when their work lands, the spec's number and its matrix row move in one edit and the gate keeps its teeth.
- Scratch install coordinates, verbatim: database `myshop_tutorial`, HTTP `http://127.0.0.1:8010`, Celery broker/backend Redis database index **15**, task queue **`tutorial`**.
- No file under `core/`, `authapp/`, `templates/`, `myshopproject/` or `scripts/services/` is created or edited. This lane writes only `docs/onboarding/**`, `docs/superpowers/**`, `scripts/__init__.py`, `scripts/tutorial/**`, `pyproject.toml`, `uv.lock`.
- Playwright is a **dev-group** dependency (`[dependency-groups]`), Chromium only, sync API only. Viewports are `desktop` 1440×900 and `phone` 390×844 — no other size is captured.
- Every entry point that touches data calls `isolation.assert_isolated()` first. It reads **resolved settings**, never the environment, because `myshopproject/settings.py:13` runs `load_dotenv(BASE_DIR / ".env", override=True)` and `.env` carries `POSTGRES_DB` and both `CELERY_*` URLs.
- The only two sanctioned ways to run this lane's modules: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.<module> …` (always `-m`, from the repo root — a direct file path breaks the `scripts.tutorial` imports) and `.venv/Scripts/python.exe manage.py <cmd> --settings=scripts.tutorial.demo_settings …`. `_guard()` refuses if `DJANGO_SETTINGS_MODULE` is not exactly the shim and never defaults it, so no module can guess its way onto the shop's database.
- Recipes write through the real services (`core.checkout.checkout`, `core.inventory.receive_stock`, `core.inventory.adjust_batch`). The only sanctioned bypass is `QuerySet.update()`, and only for the two states the services refuse to produce: `out-of-balance` and `after-hours`.
- Recipes write files as well as rows: `catalogue()` puts the tutorial's own product photo under `MEDIA_ROOT`. Every test that calls a recipe therefore lives in `scripts/tutorial/tests/test_seed_recipes.py`, which redirects `MEDIA_ROOT` to a temp folder in `setUpModule` — or, for the one module created later (Task 22's `test_receipt_preview.py`), repeats that redirect. The lane's test command runs on the **live** settings, whose `MEDIA_ROOT` is the shop's real `media/`; a new test module that seeds without the redirect drops a demo picture next to the shop's product photos.
- Captions describe what is in the frame; steps instruct. Currency is written as the screen writes it (`GH₵`); where the app prints `GHs`, quote it verbatim and add a note — never silently correct it.
- A feature with no UI is stated as an absence in that chapter's "Notes & limits". It never becomes a step.
- PNGs are committed alongside the Markdown (owner decision 2026-11-03).
- Worktree etiquette: stage explicit paths only, never `git add -A`; run one test suite at a time; another live session edits `core/` in this tree, so re-check any `core/views.py` line citation immediately before using it; local commits only — no push, no merge, no branch switch.
- Test command for this lane's Python: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial`. Full-suite command: `.venv/Scripts/python.exe manage.py test --keepdb`. Redirect to a file and read the exit code — Django prints results on stderr and a pipe hides the verdict.

## File Structure

```
scripts/__init__.py                     makes scripts.tutorial importable by the test runner
scripts/tutorial/__init__.py            package marker
scripts/tutorial/isolation.py           the scratch coordinates + assert_isolated() — the only
                                        module that knows what "safe to write to" means
scripts/tutorial/demo_settings.py       settings shim: star-import, then override DB/broker/queue
scripts/tutorial/scratchdb.py           CREATE DATABASE for the scratch name, guard first
scripts/tutorial/run_demo_server.ps1    create + migrate + :8010 runserver + tutorial-queue worker
scripts/tutorial/seed_demo.py           recipe registry, --reset/--list/--only CLI, the recipes the
                                        spec names plus the states each chapter adds
scripts/tutorial/shoot.py               manifest reader, two logged-in contexts, step replay,
                                        PNG writer, SHOTLOG.md generator
scripts/tutorial/shots.json             the manifest: every shot, its role, viewport, recipe, steps
scripts/tutorial/verify.py              the four gates + the placeholder resolver
scripts/tutorial/tests/__init__.py
scripts/tutorial/tests/test_isolation.py
scripts/tutorial/tests/test_demo_settings.py
scripts/tutorial/tests/test_seed_recipes.py
scripts/tutorial/tests/test_shoot_manifest.py
scripts/tutorial/tests/test_verify_gates.py
docs/onboarding/README.md               index + how to re-shoot (written in Phase 6)
docs/onboarding/_template.md            the five-block anatomy every chapter copies
docs/onboarding/NN-<slug>.md            the thirteen chapters
docs/onboarding/img/<NN>-<slug>/NN-slug.png
docs/onboarding/samples/                the real downloads, each under the filename its own
                                        Content-Disposition carried (Invoice-*.pdf per
                                        core/views.py:1363, Sale_*.pdf per :1301, Reports_*.pdf per
                                        :1569, orders_*.csv, sales_report_*.csv) + receipt-preview.html
docs/onboarding/SHOTLOG.md              generated by shoot.py; never hand-edited
```

Responsibility boundaries worth holding: `isolation.py` knows the coordinates and nothing else; `scratchdb.py` knows how to create the one database it is allowed to create; `seed_demo.py` knows how to make state and never opens a browser; `shoot.py` knows how to drive a page and never writes application data directly; `verify.py` reads artifacts and the URLconf and writes nothing.

---

# Phase 0 — The engine

The exit condition is a proof, not a promise: the Receive Delivery dialog captured over the ledger at both viewports, one shot per cookie jar, and a coverage matrix with all 59 entries filled. No published prose.

### Task 1: The isolation shim and its guard

**Files:**
- Create: `scripts/__init__.py`, `scripts/tutorial/__init__.py`, `scripts/tutorial/tests/__init__.py`
- Create: `scripts/tutorial/isolation.py`
- Create: `scripts/tutorial/demo_settings.py`
- Test: `scripts/tutorial/tests/test_isolation.py`, `scripts/tutorial/tests/test_demo_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: constants `SCRATCH_DB`, `SHIM_MODULE`, `DEMO_HOST`, `SCRATCH_PORT`, `BROKER_DB_INDEX`, `TUTORIAL_QUEUE`, `DEMO_MEDIA_FOLDER`, `DEMO_BASE_URL`; exception `NotScratchInstall`; `assert_isolated(settings, base_url=None) -> None`; settings module `scripts.tutorial.demo_settings` with `DATABASES["default"]["NAME"] == "myshop_tutorial"` (in a dict of its own, never by mutating the live one), `CELERY_TASK_DEFAULT_QUEUE == "tutorial"`, both Celery URLs ending `/15`, and `MEDIA_ROOT` one folder below the shop's `media/`. The guard checks all five, so the shim cannot silently drop a coordinate.

- [ ] **Step 1: Write the failing tests**

`scripts/tutorial/tests/test_isolation.py`:

```python
from types import SimpleNamespace

from django.test import SimpleTestCase

from scripts.tutorial import isolation


def scratch(**overrides):
    """A settings object that passes the guard unless a test breaks it."""
    base = {
        "DATABASES": {"default": {"NAME": isolation.SCRATCH_DB}},
        "CELERY_BROKER_URL": "redis://127.0.0.1:6379/15",
        "CELERY_RESULT_BACKEND": "redis://127.0.0.1:6379/15",
        "CELERY_TASK_DEFAULT_QUEUE": "tutorial",
        "MEDIA_ROOT": f"C:/shop/media/{isolation.DEMO_MEDIA_FOLDER}",
    }
    return SimpleNamespace(**{**base, **overrides})


class AssertIsolatedTests(SimpleTestCase):
    def test_accepts_a_fully_isolated_install(self):
        isolation.assert_isolated(scratch())

    def test_names_the_live_database_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "myshopproject"):
            isolation.assert_isolated(
                scratch(DATABASES={"default": {"NAME": "myshopproject"}}),
            )

    def test_names_a_shared_redis_index_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "index"):
            isolation.assert_isolated(scratch(CELERY_BROKER_URL="redis://127.0.0.1:6379"))

    def test_names_a_shared_queue_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "queue"):
            isolation.assert_isolated(scratch(CELERY_TASK_DEFAULT_QUEUE="celery"))

    def test_names_a_live_server_port_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "8010"):
            isolation.assert_isolated(scratch(), base_url="http://127.0.0.1:8000")

    def test_names_a_lookalike_port_as_a_problem(self):
        """A substring match would read ':8010' inside ':80100' and wave it through."""
        with self.assertRaisesRegex(isolation.NotScratchInstall, "base URL"):
            isolation.assert_isolated(scratch(), base_url="http://127.0.0.1:80100")

    def test_names_another_host_on_the_scratch_port_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "base URL"):
            isolation.assert_isolated(scratch(), base_url="http://localhost:8010")

    def test_accepts_the_base_url_it_publishes(self):
        isolation.assert_isolated(scratch(), base_url=isolation.DEMO_BASE_URL)

    def test_names_the_shops_media_folder_as_a_problem(self):
        """The guard is what makes the shim's MEDIA_ROOT override a requirement
        rather than a preference: a demo upload that lands in media/products is a
        write into the shop's own pictures."""
        with self.assertRaisesRegex(isolation.NotScratchInstall, "media"):
            isolation.assert_isolated(scratch(MEDIA_ROOT="C:/shop/media"))

    def test_names_a_missing_media_folder_as_a_problem(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "media"):
            isolation.assert_isolated(scratch(MEDIA_ROOT=""))

    def test_refuses_an_unparsable_base_url(self):
        with self.assertRaisesRegex(isolation.NotScratchInstall, "base URL"):
            isolation.assert_isolated(scratch(), base_url="127.0.0.1:8010")

    def test_reports_settings_it_cannot_read_instead_of_crashing(self):
        """A launcher that passes the wrong object must be refused, not trace-backed."""
        with self.assertRaisesRegex(isolation.NotScratchInstall, "database"):
            isolation.assert_isolated(SimpleNamespace())

    def test_a_live_database_is_refused_even_with_a_scratch_url(self):
        """The two checks are independent: a scratch port does not excuse the shop's books."""
        with self.assertRaisesRegex(isolation.NotScratchInstall, "database"):
            isolation.assert_isolated(
                scratch(DATABASES={"default": {"NAME": "myshopproject"}}),
                base_url=isolation.DEMO_BASE_URL,
            )
```

`scripts/tutorial/tests/test_demo_settings.py`:

```python
from pathlib import Path

from django.test import SimpleTestCase


class DemoSettingsTests(SimpleTestCase):
    """The shim is the whole safety story, so its values are asserted, not assumed:
    .env re-applies POSTGRES_DB and both CELERY_* URLs over any exported value."""

    def setUp(self):
        from scripts.tutorial import demo_settings

        self.demo_settings = demo_settings

    def test_points_at_the_scratch_database(self):
        self.assertEqual(
            self.demo_settings.DATABASES["default"]["NAME"], "myshop_tutorial"
        )

    def test_moves_the_broker_onto_its_own_redis_index(self):
        self.assertTrue(self.demo_settings.CELERY_BROKER_URL.endswith("/15"))
        self.assertTrue(self.demo_settings.CELERY_RESULT_BACKEND.endswith("/15"))

    def test_gives_demo_tasks_a_queue_the_shop_worker_never_reads(self):
        self.assertEqual(self.demo_settings.CELERY_TASK_DEFAULT_QUEUE, "tutorial")

    def test_keeps_the_project_secret_key_and_apps(self):
        from myshopproject import settings

        self.assertEqual(self.demo_settings.INSTALLED_APPS, settings.INSTALLED_APPS)
        self.assertEqual(self.demo_settings.AUTH_USER_MODEL, settings.AUTH_USER_MODEL)

    def test_does_not_rename_the_live_projects_database(self):
        """The deviation from the plan, guarded: the star-import binds the *same*
        dict myshopproject.settings holds, so writing
        DATABASES["default"]["NAME"] = SCRATCH_DB would retarget the shop's own
        connection in every process that merely imported this shim."""
        from myshopproject import settings

        self.assertIsNot(self.demo_settings.DATABASES, settings.DATABASES)
        self.assertNotEqual(settings.DATABASES["default"]["NAME"], "myshop_tutorial")

    def test_gives_demo_uploads_their_own_media_folder(self):
        """A photo uploaded through the product dialog would otherwise be written
        among the shop's real product pictures, next door in media/products/."""
        from myshopproject import settings

        demo = Path(self.demo_settings.MEDIA_ROOT)
        live = Path(settings.MEDIA_ROOT)
        self.assertNotEqual(demo, live)
        self.assertTrue(
            demo.is_relative_to(live),
            "the scratch media folder stays under media/, which .gitignore already covers",
        )

    def test_the_guard_passes_the_install_it_describes(self):
        """The shim and the guard move independently. If one changes a coordinate
        and the other does not, every entry point refuses to run — so the refusal
        has to be proven against the real settings object, not only the fakes."""
        from scripts.tutorial import isolation

        isolation.assert_isolated(self.demo_settings)
```

- [ ] **Step 2: Run them to watch them fail**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0.log 2>&1; echo "exit=$?"`
Expected: `exit=1`. `scripts/` already exists (it holds the other lane's PowerShell) and Python treats it as a namespace package, so the failure is `ImportError: cannot import name 'isolation' from 'scripts.tutorial'` — not `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Create the packages and write `isolation.py`**

`scripts/__init__.py` and `scripts/tutorial/__init__.py` and `scripts/tutorial/tests/__init__.py` are each one comment line:

```python
# Tutorial capture harness. Not imported by the running shop.
```

`scripts/tutorial/isolation.py`:

```python
"""The only module that says what 'safe to write demo data' means.

Every entry point calls assert_isolated() before touching anything, and it reads
resolved settings rather than os.environ: myshopproject/settings.py loads .env
with override=True, so an exported POSTGRES_DB loses to the file and a launcher
that trusted the environment would have run its migrations against the shop's
own books.
"""

from pathlib import Path
from urllib.parse import urlsplit

SCRATCH_DB = "myshop_tutorial"
SHIM_MODULE = "scripts.tutorial.demo_settings"
DEMO_HOST = "127.0.0.1"
SCRATCH_PORT = 8010
DEMO_BASE_URL = f"http://{DEMO_HOST}:{SCRATCH_PORT}"
BROKER_DB_INDEX = 15
TUTORIAL_QUEUE = "tutorial"
DEMO_MEDIA_FOLDER = "_tutorial"


class NotScratchInstall(Exception):
    """Refuse to write, shoot or migrate: this process is not the demo install."""


def assert_isolated(settings, base_url=None):
    problems = []
    try:
        name = settings.DATABASES["default"]["NAME"]
    except (AttributeError, KeyError, TypeError):
        problems.append("database name is unreadable from these settings")
    else:
        if name != SCRATCH_DB:
            problems.append(
                f"database is {name!r}, expected the scratch {SCRATCH_DB!r}"
            )
    for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        value = str(getattr(settings, key, ""))
        if not value.endswith(f"/{BROKER_DB_INDEX}"):
            problems.append(
                f"{key} shares the shop's Redis index, expected .../{BROKER_DB_INDEX}"
            )
    queue = getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "celery")
    if queue != TUTORIAL_QUEUE:
        problems.append(f"task queue is {queue!r}, expected the demo {TUTORIAL_QUEUE!r}")
    media = str(getattr(settings, "MEDIA_ROOT", ""))
    if Path(media).name != DEMO_MEDIA_FOLDER:
        problems.append(
            f"media root is {media!r}, expected a .../{DEMO_MEDIA_FOLDER} folder of its own"
        )
    if base_url is not None and not _is_scratch_server(base_url):
        problems.append(
            f"base URL {base_url!r} is not the scratch server on port {SCRATCH_PORT}"
        )
    if problems:
        raise NotScratchInstall(
            "not the isolated tutorial install: " + "; ".join(problems)
            + f". Run with --settings={SHIM_MODULE}."
        )


def _is_scratch_server(base_url):
    """Parsed, not substringed: ':8010' hides inside ':80100', and a port alone
    never says whose server the URL points at."""
    try:
        target = urlsplit(base_url)
        return (target.hostname, target.port) == (DEMO_HOST, SCRATCH_PORT)
    except ValueError:
        return False
```

- [ ] **Step 4: Write `demo_settings.py`**

```python
"""Settings for the disposable tutorial install. Never used by the shop.

Star-importing the project settings runs its load_dotenv(..., override=True), so
every override below is applied after .env has had its say and therefore wins.
"""

from pathlib import Path

from myshopproject.settings import *  # noqa: F403

from scripts.tutorial.isolation import (
    BROKER_DB_INDEX,
    DEMO_MEDIA_FOLDER,
    SCRATCH_DB,
    TUTORIAL_QUEUE,
)

# A new dict, not a mutation of the imported one: the star-import binds the same
# object myshopproject.settings holds, and a test process that imports this shim
# would otherwise rename the live connection mid-run.
DATABASES = {  # noqa: F405
    **DATABASES,  # noqa: F405
    "default": {**DATABASES["default"], "NAME": SCRATCH_DB},  # noqa: F405
}

_broker = f"redis://127.0.0.1:6379/{BROKER_DB_INDEX}"
CELERY_BROKER_URL = _broker
CELERY_RESULT_BACKEND = _broker
CELERY_TASK_DEFAULT_QUEUE = TUTORIAL_QUEUE

# One folder below the shop's own photos, not beside them: media/ is git-ignored as
# a whole, so the scratch tree stays untracked without touching .gitignore.
MEDIA_ROOT = str(Path(MEDIA_ROOT) / DEMO_MEDIA_FOLDER)  # noqa: F405
```

- [ ] **Step 5: Run the tests to green**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0.log 2>&1; echo "exit=$?"`
Expected: `exit=0`, `Ran 20 tests` (thirteen guard tests and seven shim tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/tutorial/__init__.py scripts/tutorial/tests/__init__.py \
        scripts/tutorial/isolation.py scripts/tutorial/demo_settings.py \
        scripts/tutorial/tests/test_isolation.py scripts/tutorial/tests/test_demo_settings.py
git commit -m "Isolate the tutorial install in settings, not in the environment"
```

### Task 2: The launcher that brings the scratch install up

**Files:**
- Create: `scripts/tutorial/scratchdb.py`, `scripts/tutorial/run_demo_server.ps1`
- Modify: `pyproject.toml`, `uv.lock` (dev-group Playwright, so the launcher can assume `.venv` is complete)

**Interfaces:**
- Consumes: `scripts.tutorial.isolation` constants through `--settings=scripts.tutorial.demo_settings`.
- Produces: a running `http://127.0.0.1:8010` and a `tutorial`-queue worker, both from `.venv`; the log pair `%LOCALAPPDATA%\myshop-tutorial\server.log` and `worker.log`.

- [ ] **Step 1: Add the dev dependency**

Run: `uv add --group dev playwright`
Expected: a `[dependency-groups]` block with `dev = ["playwright>=<resolved>"]` appears in `pyproject.toml`, `uv.lock` updates, `.venv` gains `playwright`. Do not hand-write a version floor — let `uv` resolve one. Confirm nothing moved in `[project] dependencies`:

Run: `git diff -- pyproject.toml`
Expected: only the new `[dependency-groups]` block and the `uv.lock` refresh; no `^-` line touching an existing runtime dependency.

- [ ] **Step 2: Install the browser once**

Run: `.venv/Scripts/python.exe -m playwright install chromium`
Expected: a ~130 MB download into `%LOCALAPPDATA%\ms-playwright`. This is the one-time cost the owner approved; if it fails offline, stop and report — every later phase needs it.

- [ ] **Step 3: Write the scratch-database helper**

`scripts/tutorial/scratchdb.py`:

```python
"""Create the scratch database, from resolved settings and nowhere else.

assert_isolated() runs before the maintenance connection opens, so pointing this
at myshopproject.settings cannot create, touch or name the shop's database. The
name reaches CREATE DATABASE through conn.ops.quote_name(), so there is no
string interpolation of a user-supplied value.
"""

from scripts.tutorial.isolation import assert_isolated


def ensure_scratch_database() -> str:
    from django.conf import settings
    from django.db import connections

    assert_isolated(settings)
    name = settings.DATABASES["default"]["NAME"]
    conn = connections["default"]
    with conn._nodb_cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name])
        if cursor.fetchone():
            return f"{name} already present"
        cursor.connection.autocommit = True
        cursor.execute(f"CREATE DATABASE {conn.ops.quote_name(name)}")
    return f"created {name}"
```

`_nodb_cursor()` is Django's own "connect to the maintenance database" path — the same one the test runner uses. Do not replace it with a psycopg2 connection built from `.env`, which is precisely the hand-rolled environment reading this plan exists to avoid.

- [ ] **Step 4: Write the launcher**

`scripts/tutorial/run_demo_server.ps1`:

```powershell
<#
    Brings up the disposable tutorial install: database myshop_tutorial, server on
    :8010, worker on the tutorial queue. The shop's own :8000/:8001 servers and its
    worker are never signalled by this script.
#>
[CmdletBinding()]
param(
    [switch]$NoWorker
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Settings = 'scripts.tutorial.demo_settings'

# DJANGO_SETTINGS_MODULE is exported before any child process starts, because
# myshopproject/celery.py only setdefaults it and .env re-asserts its own values
# over the environment. A worker launched without this would read the shop's
# broker URL and its queue.
$env:DJANGO_SETTINGS_MODULE = $Settings

$LogDir = Join-Path $env:LOCALAPPDATA 'myshop-tutorial'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $Repo

# 1. Resolve, then refuse. The guard reads settings Django has already loaded,
#    so a .env override cannot slip past it.
& $Python manage.py shell --settings=$Settings -c "from django.conf import settings; from scripts.tutorial.isolation import assert_isolated; assert_isolated(settings); print('scratch install:', settings.DATABASES['default']['NAME'], settings.CELERY_TASK_DEFAULT_QUEUE)"
if ($LASTEXITCODE -ne 0) { throw 'refused: the resolved settings are not the scratch install' }

# 2. CREATE DATABASE for the scratch name only.
& $Python manage.py shell --settings=$Settings -c "from scripts.tutorial.scratchdb import ensure_scratch_database; print(ensure_scratch_database())"
if ($LASTEXITCODE -ne 0) { throw 'could not create the scratch database' }

# 3. Schema.
& $Python manage.py migrate --settings=$Settings --no-input

# 4. Worker first, then the server in the foreground: runserver never returns, so
#    anything after it below would be unreachable. Closing this terminal stops the
#    server; the tutorial worker is stopped by step 6.
if (-not $NoWorker) {
    Start-Process -FilePath $Python `
        -ArgumentList '-m', 'celery', '-A', 'myshopproject', 'worker',
                     '-Q', 'tutorial', '-l', 'INFO' `
        -WorkingDirectory $Repo `
        -RedirectStandardOutput (Join-Path $LogDir 'worker.log') `
        -RedirectStandardError (Join-Path $LogDir 'worker.err.log')
    Write-Host "tutorial worker started; log at $LogDir\worker.log"
}

Write-Host 'serving http://127.0.0.1:8010 (Ctrl+C to stop; see step 6 for the worker)'
& $Python manage.py runserver 127.0.0.1:8010 --settings=$Settings --nothreading --noreload
```

`--nothreading --noreload` keeps one htmx-friendly process and stops the autoreloader from re-executing the Celery-starting parent. Step 6 of this task is the only sanctioned way to stop the worker, and it filters on `-Q tutorial` so it cannot hit the shop's worker.

- [ ] **Step 5: Prove it refuses the live database**

Run: `powershell -NoProfile -Command "$env:DJANGO_SETTINGS_MODULE='myshopproject.settings'; & .venv\Scripts\python.exe manage.py shell --settings=myshopproject.settings -c \"from django.conf import settings; from scripts.tutorial.isolation import assert_isolated; assert_isolated(settings)\""`
Expected: `NotScratchInstall: not the isolated tutorial install: database is 'myshopproject', expected the scratch 'myshop_tutorial'; ...` — and no connection attempt, because the guard precedes it.

- [ ] **Step 6: Prove the scratch install answers**

Run: `powershell -NoProfile -File scripts/tutorial/run_demo_server.ps1` (own terminal, leave it running)
Then: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8010/login/`
Expected: `200`, and the launcher's own guard line printed before it, naming `myshop_tutorial` and `tutorial`. Confirm the shop's server was untouched: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login/` → `200`. Confirm the scratch install is empty, which is what proves the two databases are different: `curl -s http://127.0.0.1:8010/login/ | grep -c "Noble"` and the same against `:8000` differ, and `:8010` has no products yet.

- [ ] **Step 7: Stop only the tutorial worker**

Run: `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*-Q tutorial*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -WhatIf }"`
Expected: the `-WhatIf` output names exactly one process, whose command line carries `-Q tutorial`. The shop's worker command line has no `-Q tutorial`, so it cannot match. Re-run with `-WhatIf` removed only when that listing is right — and only when the chapters need the worker stopped; the launcher leaves it running on purpose.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock scripts/tutorial/scratchdb.py scripts/tutorial/run_demo_server.ps1
git commit -m "Add the launcher that starts the disposable tutorial install"
```

### Task 3: The chapter template and the index skeleton

**Files:**
- Create: `docs/onboarding/_template.md`
- Create: `docs/onboarding/README.md` (stub in Phase 0, finished in Phase 6)
- Create: `docs/onboarding/img/.gitkeep`, `docs/onboarding/samples/.gitkeep`

**Interfaces:**
- Consumes: the spec's "Chapter anatomy".
- Produces: the five block headings every chapter task copies verbatim: `## What this is for`, `## You need`, `## Steps`, `## When it goes wrong`, `## Notes & limits`.

- [ ] **Step 1: Write the template**

`docs/onboarding/_template.md`:

```markdown
# NN — Chapter title

<!-- Copy this file to NN-<slug>.md. Delete the HTML comments when the chapter is done.
     Every block is required; a chapter with an empty "When it goes wrong" is a chapter
     nobody has used yet. -->

## What this is for

<!-- Two or three sentences in shop words. No route, no model name, no "the system". -->

## You need

- **Role:** Owner / Cashier / Either
- **Screen:** where it lives
- **Getting there:** the clicks from the hub, in the order a person performs them
- **Data that must already exist:** the recipe names from `seed_demo.py --list`

## Steps

<!-- One screenshot per step. The caption says only what is visible in the frame. -->

![step one: what the reader should see](img/NN-chapter/01-slug.png)

1. What to press.

## When it goes wrong

<!-- Quote the app's own words verbatim, then one line of what it means for the shop.
     If the app says GHs, quote GHs and note it. -->

## Notes & limits

<!-- What this screen will never do, what its label overpromises, and what only the
     other role can see. -->
```

- [ ] **Step 2: Write the stub index**

`docs/onboarding/README.md`:

```markdown
# Noble Cosmetics — onboarding manual

Not written yet. Phase 0 builds the capture engine; chapters arrive in Phases 1–6 and
this index is generated last, from the files that exist.

See [the design](../superpowers/specs/2026-11-03-onboarding-tutorial-design.md) for what
this will contain and [the plan](../superpowers/plans/2026-11-04-onboarding-tutorial.md)
for how it is built.
```

- [ ] **Step 3: Commit**

```bash
git add docs/onboarding/_template.md docs/onboarding/README.md docs/onboarding/img/.gitkeep docs/onboarding/samples/.gitkeep
git commit -m "Add the chapter anatomy every onboarding chapter must follow"
```

### Task 4: The seeder's spine and the `people` recipe

**Files:**
- Create: `scripts/tutorial/seed_demo.py`
- Test: `scripts/tutorial/tests/test_seed_recipes.py`

**Interfaces:**
- Consumes: `isolation.assert_isolated`, `authapp.models.Account`.
- Produces: `REGISTRY: dict[str, object]` (seed callables keyed by recipe name), `run(recipes: list[str]) -> None`, `people() -> dict[str, str]` returning `{"owner": ..., "cashier": ..., "quiet": ...}` usernames; the constants `OWNER_USERNAME = "demo.owner"`, `CASHIER_USERNAME = "demo.rep"`, `DEACTIVATED_USERNAME = "demo.locked"`, `DEMO_PASSWORD = "Tut0rial-Str0ng-Pass!"`.

- [ ] **Step 1: Write the failing tests**

`scripts/tutorial/tests/test_seed_recipes.py`:

```python
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from scripts.tutorial import seed_demo

_media = None
_override = None


def setUpModule():
    """Every class in this module seeds, and the catalogue writes the tutorial's own
    product photo. `manage.py test` runs on the live settings, whose MEDIA_ROOT is the
    shop's real `media/` — so the folder is redirected once for the whole module, which
    also covers the classes Tasks 12–28 append here. Verified on this tree: the override
    is still applied in a second class of the same module."""
    global _media, _override
    _media = tempfile.TemporaryDirectory(prefix="tutorial-media-")
    _override = override_settings(MEDIA_ROOT=_media.name)
    _override.enable()


def tearDownModule():
    _override.disable()
    _media.cleanup()


class PeopleRecipeTests(TestCase):
    def test_makes_the_three_accounts_the_jars_need(self):
        names = seed_demo.people()

        self.assertEqual(
            set(names), {"owner", "cashier", "quiet"}
        )
        Account = get_user_model()
        self.assertEqual(Account.objects.get(username=names["owner"]).user_type, "ADMIN")
        self.assertEqual(
            Account.objects.get(username=names["cashier"]).user_type, "SALEPERSON"
        )

    def test_the_third_account_is_locked_at_the_door(self):
        Account = get_user_model()
        names = seed_demo.people()

        self.assertFalse(Account.objects.get(username=names["quiet"]).is_active)

    def test_the_names_land_so_the_roster_shows_people_not_handles(self):
        Account = get_user_model()
        seed_demo.people()

        self.assertEqual(
            Account.objects.get(username=seed_demo.CASHIER_USERNAME).get_full_name(),
            "Afia Mensah",
        )

    def test_the_password_passes_the_project_validators(self):
        from django.contrib.auth.password_validation import validate_password

        validate_password(seed_demo.DEMO_PASSWORD)

    def test_the_registry_is_a_name_to_recipe_map(self):
        self.assertIn("people", seed_demo.REGISTRY)
        self.assertTrue(callable(seed_demo.REGISTRY["people"]))
        # all eleven names are asserted in Task 21, where the last recipe lands —
        # asserting them here would fail for a reason that is not a defect
```

- [ ] **Step 2: Run to watch them fail**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial.tests.test_seed_recipes > /tmp/p0b.log 2>&1; echo "exit=$?"`
Expected: `exit=1`, `ImportError` / `module 'scripts.tutorial.seed_demo' has no attribute 'people'`.

- [ ] **Step 3: Write the spine**

`scripts/tutorial/seed_demo.py`:

```python
"""Build the state each chapter is photographed in, on the scratch install only.

Recipes call the real services so FIFO allocations, frozen line costs and the
batch/shelf invariant are genuinely produced. A tutorial whose numbers were typed
in would teach the wrong thing.
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

from scripts.tutorial.isolation import SHIM_MODULE

OWNER_USERNAME = "demo.owner"
CASHIER_USERNAME = "demo.rep"
DEACTIVATED_USERNAME = "demo.locked"
DEMO_PASSWORD = "Tut0rial-Str0ng-Pass!"


def _guard() -> None:
    """Refuse to run unless the caller named the shim, then assert what it resolved.

    Two checks, in this order: the settings module must already be the shim (so an
    accidental `myshopproject.settings` never even reaches django.setup()), and the
    resolved settings must pass assert_isolated() (so a shim edited later, or a .env
    value re-asserting itself, cannot slip through). Nothing here defaults the module
    — a seeder that guessed which settings to load is the failure mode this whole
    lane is built to avoid.
    """
    if os.environ.get("DJANGO_SETTINGS_MODULE") != SHIM_MODULE:
        raise SystemExit(
            f"run with DJANGO_SETTINGS_MODULE={SHIM_MODULE} (or --settings={SHIM_MODULE}); "
            "the shop's books are not a studio"
        )
    import django

    django.setup()
    from django.conf import settings

    from scripts.tutorial.isolation import assert_isolated

    assert_isolated(settings)


def people() -> dict[str, str]:
    from django.contrib.auth import get_user_model

    Account = get_user_model()
    for username, full_name, user_type, active in (
        (OWNER_USERNAME, "Demo Owner", "ADMIN", True),
        (CASHIER_USERNAME, "Afia Mensah", "SALEPERSON", True),
        (DEACTIVATED_USERNAME, "Kofi Locked", "SALEPERSON", False),
    ):
        first, _, last = full_name.partition(" ")
        Account.objects.filter(username=username).delete()
        account = Account(
            username=username, first_name=first, last_name=last,
            user_type=user_type, is_active=active,
            email=f"{username}@example.invalid", telephone="0244000000",
        )
        account.set_password(DEMO_PASSWORD)
        account.save()
    return {"owner": OWNER_USERNAME, "cashier": CASHIER_USERNAME, "quiet": DEACTIVATED_USERNAME}


REGISTRY: dict[str, object] = {"people": people}


def run(recipes: list[str]) -> None:
    for name in recipes:
        REGISTRY[name]()
        print(f"seeded {name}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show the recipe names")
    parser.add_argument("--reset", nargs="*", default=None, metavar="RECIPE")
    parser.add_argument("--only", nargs="*", default=None, metavar="RECIPE")
    args = parser.parse_args(argv)

    if args.list:
        for name in sorted(REGISTRY):
            print(name)
        return 0

    _guard()
    if args.reset is not None:
        from scripts.tutorial.teardown import wipe

        wipe()
        run(args.reset or sorted(REGISTRY))
    elif args.only:
        run(args.only)
    else:
        parser.error("nothing to do: pass --reset or --only")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`--reset` needs `teardown.wipe()`, which is Task 4's second file — write it now so the module imports:

`scripts/tutorial/teardown.py`:

```python
"""Delete demo state in dependency order so a reset can re-run every recipe.

Migrations and the schema survive; only rows go. This runs under the shim, so the
shop's own database cannot be reached from here.
"""

MODELS_IN_ORDER = [
    "core.SaleBatchAllocation",
    "core.StockAdjustment",
    "core.StockBatch",
    "core.StockReceipt",
    "core.StockReceiptDraft",
    "core.ProductImportOperation",
    "core.OrderItem",
    "core.Order",
    "core.Product",
    "authapp.Account",
]


def wipe() -> None:
    from django.apps import apps
    from django.db import transaction

    with transaction.atomic():
        for label in MODELS_IN_ORDER:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            deleted, _ = model.objects.all().delete()
            if deleted:
                print(f"wiped {deleted} {label}")
```

These ten labels are the whole model inventory of `core/models.py` (verified 2026-11-04: eleven classes, two of which — `ProductCategory` and `StockReceiptSource` — are `TextChoices`, not tables), ordered by the `on_delete=PROTECT` edges: allocations and adjustments guard batches, batches guard receipts, receipts guard drafts and `ProductImportOperation`/`Order` guard their accounts. If a future migration adds a model with a PROTECT edge into this set, `wipe()` raises IntegrityError — add it to the list above rather than catching the error.

- [ ] **Step 4: Run to green**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0c.log 2>&1; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 5: Prove the guard actually stops a live run**

These modules are run with `-m` from the repository root, never as `python scripts/tutorial/seed_demo.py` — a direct file run puts `scripts/tutorial` on `sys.path`, not the repo root, so `scripts.tutorial.*` imports fail for a reason that has nothing to do with safety.

Run: `DJANGO_SETTINGS_MODULE=myshopproject.settings .venv/Scripts/python.exe -m scripts.tutorial.seed_demo --reset people`
Expected: exits before Django starts, with `run with DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings (or --settings=scripts.tutorial.demo_settings); the shop's books are not a studio`. Nothing is read, nothing is written.

Run: `.venv/Scripts/python.exe -m scripts.tutorial.seed_demo --reset people`
Expected: the same refusal — an unset module is not a safe default.

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.seed_demo --reset people`
Expected: `wiped N authapp.Account` (if anything was there), then `seeded people`, and the launcher's scratch database now holds three demo accounts.

Then the equivalent through Django's own runner, which is the form the later tasks use:

Run: `.venv/Scripts/python.exe manage.py shell --settings=scripts.tutorial.demo_settings -c "from scripts.tutorial import seed_demo; print(seed_demo.people())"`
Expected: `{'owner': 'demo.owner', 'cashier': 'demo.rep', 'quiet': 'demo.locked'}` and nothing about the shop's `kb`/`sales` accounts, which do not exist in `myshop_tutorial`. Confirm that on the live install with `--settings=myshopproject.settings` the same command refuses (`SystemExit`) rather than printing.

- [ ] **Step 6: Commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/teardown.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Seed the demo people through the real account model"
```

### Task 5: The `catalogue` and `opening` recipes

**Files:**
- Modify: `scripts/tutorial/seed_demo.py`
- Test: `scripts/tutorial/tests/test_seed_recipes.py`

**Interfaces:**
- Consumes: `Product`, `ProductCategory`, `receive_stock(...)` with `source=StockReceiptSource.OPENING`.
- Produces: `catalogue() -> list[Product]`, `opening() -> None`, `DEMO_SKUS: list[str]`, and the helper `make_product(name, *, category, price, cost, threshold=5, sku=None) -> Product`.

- [ ] **Step 1: Write the failing tests**

```python
class CatalogueRecipeTests(TestCase):
    """No `setUp` here: the module fixture created in Task 4 already moved
    `MEDIA_ROOT` out of the shop's `media/` for every class in this file."""

    def test_every_category_is_represented(self):
        from core.models import ProductCategory

        products = seed_demo.catalogue()

        self.assertEqual(
            {p.category for p in products}, {c.value for c in ProductCategory}
        )

    def test_the_shelf_has_a_depleted_and_a_low_product(self):
        from core.models import Product

        seed_demo.catalogue()
        seed_demo.opening()

        self.assertTrue(Product.objects.filter(stock=0).exists())
        low = Product.objects.exclude(stock=0).order_by("stock").first()
        self.assertLessEqual(low.stock, low.low_stock_threshold)

    def test_the_ledger_shows_both_image_states(self):
        """One frame needs the monogram fallback, the next a real photo — and the
        photo is the tutorial's own file, never one of the shop's product pictures."""
        from django.conf import settings

        from core.models import Product

        seed_demo.catalogue()

        self.assertTrue(Product.objects.filter(image__isnull=True).exists())
        photo = Product.objects.exclude(image__isnull=True).get()
        self.assertTrue(Path(settings.MEDIA_ROOT, photo.image.name).is_file())

    def test_profit_rate_follows_the_importer_formula(self):
        from core.catalog_imports import PROFIT_RATE_MAX
        from core.models import Product

        product = seed_demo.catalogue()[0]

        self.assertEqual(
            product.profit_rate,
            min(product.cost / product.price, PROFIT_RATE_MAX),
        )


class OpeningRecipeTests(TestCase):
    def test_opening_stock_produces_real_batches_and_opening_receipts(self):
        from core.models import Product, StockBatch, StockReceipt, StockReceiptSource

        seed_demo.catalogue()
        seed_demo.opening()

        self.assertTrue(StockReceipt.objects.filter(source=StockReceiptSource.OPENING).exists())
        self.assertTrue(StockBatch.objects.exists())
        for product in Product.objects.all():
            product.refresh_from_db()
            self.assertEqual(
                product.stock,
                sum(b.quantity_remaining for b in StockBatch.objects.filter(product=product)),
                f"{product.name} broke the batch/shelf invariant",
            )
```

- [ ] **Step 2: Run to watch them fail**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial.tests.test_seed_recipes > /tmp/p0d.log 2>&1; echo "exit=$?"`
Expected: `exit=1`, `AttributeError: module 'scripts.tutorial.seed_demo' has no attribute 'catalogue'`.

- [ ] **Step 3: Write the recipes**

```python
def make_product(name, *, category, price, cost, threshold=5, sku=None):
    from django.utils.text import slugify

    from core.catalog_imports import PROFIT_RATE_MAX
    from core.models import Product

    price = Decimal(price)
    cost = Decimal(cost)
    return Product.objects.create(
        name=name,
        sku=sku,
        category=category,
        low_stock_threshold=threshold,
        stock=0,  # the shelf is filled by the opening receipt, never typed
        cost=cost,
        price=price,
        profit_rate=min(cost / price, PROFIT_RATE_MAX) if price > 0 else Decimal("0.00"),
        slug=slugify(name),
    )


# (name, category, price, cost, threshold) — one depleted, one at its low point
CATALOGUE = [
    ("Hydrating Glow Elixir", "skincare", "189.00", "120.00", 6),
    ("Barrier Repair Cream", "skincare", "145.50", "98.00", 4),
    ("Velvet Matte Lip", "makeup", "79.90", "41.00", 8),
    ("Featherweight Foundation", "makeup", "210.00", "150.00", 5),
    ("Argan Shine Shampoo", "haircare", "64.00", "38.50", 10),
    ("Deep Keratin Mask", "haircare", "120.00", "72.00", 3),
    ("Amber Noir Eau de Parfum", "fragrance", "480.00", "310.00", 4),
    ("Citrus Bloom Mist", "fragrance", "155.00", "90.00", 6),
    ("Shea Bath Melt", "body", "45.00", "22.00", 12),
    ("Sea Salt Body Scrub", "body", "88.00", "55.00", 5),
]

# positional, and paired with CATALOGUE by zip(strict=True): DEMO-0001 is the
# depleted row, DEMO-0002 the one sitting exactly at its threshold
DEMO_SKUS = [f"DEMO-{index:04d}" for index in range(1, len(CATALOGUE) + 1)]


def catalogue() -> list[object]:
    products = [
        make_product(name, category=category, price=price, cost=cost, threshold=threshold)
        for (name, category, price, cost, threshold) in CATALOGUE
    ]
    for product, sku in zip(products, DEMO_SKUS, strict=True):
        product.sku = sku
        product.save(update_fields=["sku"])
    # one row carries a photo so the ledger shows both a thumb and the monogram
    # fallback. The file is generated, never borrowed: the shop's own media/ holds
    # its real product pictures, and a manual that showed them would be leaking.
    photo = _demo_photo()
    products[2].image = photo
    products[2].save(update_fields=["image"])
    return products


def _demo_photo() -> str:
    """A flat-colour PNG written under MEDIA_ROOT, returned as a relative name.

    Assigning the name instead of a File object keeps upload_to from copying it a
    second time into products/products/.
    """
    from django.conf import settings
    from PIL import Image

    folder = Path(settings.MEDIA_ROOT) / "products"
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / "demo-photo.png").exists():
        Image.new("RGB", (240, 240), (47, 94, 79)).save(folder / "demo-photo.png")
    return "products/demo-photo.png"


def opening() -> None:
    """Give the shelf a real history: OPENING receipts, and batches behind them.

    Quantities are keyed by SKU, not by position, so "which product is the depleted
    one" survives a re-sorted catalogue query.
    """
    import uuid

    from django.utils import timezone

    from core.inventory import ReceiptLine, receive_stock
    from core.models import Product, StockReceiptSource

    owner = _owner()
    for index, sku in enumerate(DEMO_SKUS):
        product = Product.objects.get(sku=sku)
        if index == 0:
            continue  # the depleted row: created, never restocked
        quantity = (
            product.low_stock_threshold
            if index == 1
            else product.low_stock_threshold * 3
        )
        receive_stock(
            actor=owner,
            request_key=uuid.uuid4(),
            lines=[ReceiptLine(product.id, quantity, product.cost)],
            received_at=timezone.localtime(),
            source=StockReceiptSource.OPENING,
            notes="Opening shelf for the tutorial install",
        )
```

`receive_stock` refuses a zero-quantity line, so the depleted row is reached by booking nothing for it — that is why `DEMO-0001` ends at `stock=0` with no batches, which is the state chapter 04's "Restock selected" and chapter 05's batch-restock refusal both need. Add the two helpers the recipes need, next to `people()`:

```python
def _owner():
    from django.contrib.auth import get_user_model

    return get_user_model().objects.get(username=OWNER_USERNAME)


def _products():
    from core.models import Product

    return list(Product.objects.order_by("name"))
```

Register both: `REGISTRY = {"people": people, "catalogue": catalogue, "opening": opening}`.

- [ ] **Step 4: Run to green**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0e.log 2>&1; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Seed a catalogue and an opening shelf through the inventory service"
```

### Task 6: The shot harness

**Files:**
- Create: `scripts/tutorial/shoot.py`
- Create: `scripts/tutorial/shots.json`
- Test: `scripts/tutorial/tests/test_shoot_manifest.py`

**Interfaces:**
- Consumes: `shots.json`, `isolation.assert_isolated`, `seed_demo` usernames.
- Produces: `load_manifest(path) -> dict`, `validate_manifest(manifest) -> list[str]`, `png_path(manifest, shot) -> Path`, `shotlog_row(shot, png, captured) -> str`, `capture(manifest, shot, page, viewport) -> Path`, `_pages(browser, manifest) -> dict[str, tuple[context, page]]`, and the CLI `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.shoot --chapter <NN|all> [--manifest <path>]`.

- [ ] **Step 1: Write the failing tests**

`scripts/tutorial/tests/test_shoot_manifest.py`:

```python
import json
from pathlib import Path

from django.test import SimpleTestCase

from scripts.tutorial import shoot

MANIFEST = Path(shoot.__file__).with_name("shots.json")


class ManifestTests(SimpleTestCase):
    def test_the_committed_manifest_is_valid(self):
        self.assertEqual(shoot.validate_manifest(shoot.load_manifest(MANIFEST)), [])

    def test_a_shot_id_is_unique(self):
        manifest = shoot.load_manifest(MANIFEST)
        manifest["shots"].append(dict(manifest["shots"][0]))

        self.assertIn("duplicate", " ".join(shoot.validate_manifest(manifest)))

    def test_a_role_must_be_declared(self):
        manifest = shoot.load_manifest(MANIFEST)
        manifest["shots"][0]["role"] = "auditor"

        self.assertIn("unknown role", " ".join(shoot.validate_manifest(manifest)))

    def test_a_viewport_must_be_declared(self):
        manifest = shoot.load_manifest(MANIFEST)
        manifest["shots"][0]["viewport"] = "tablet"

        self.assertIn("unknown viewport", " ".join(shoot.validate_manifest(manifest)))

    def test_an_unknown_action_is_refused(self):
        manifest = shoot.load_manifest(MANIFEST)
        manifest["shots"][0]["steps"] = [{"action": "hover", "selector": "body"}]

        self.assertIn("unknown action", " ".join(shoot.validate_manifest(manifest)))

    def test_the_png_lands_under_the_chapter_folder(self):
        manifest = shoot.load_manifest(MANIFEST)

        path = shoot.png_path(manifest, manifest["shots"][0])

        self.assertEqual(path.parent.name, manifest["shots"][0]["chapter"])
        self.assertEqual(path.suffix, ".png")

    def test_the_shotlog_row_carries_the_four_provenance_columns(self):
        manifest = shoot.load_manifest(MANIFEST)
        shot = manifest["shots"][0]

        row = shoot.shotlog_row(shot, "img/x/y.png", "2026-11-04T10:00:00Z")

        for column in (shot["id"], shot["role"], shot["viewport"], shot["recipe"][0]):
            self.assertIn(column, row)
```

- [ ] **Step 2: Run to watch them fail**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial.tests.test_shoot_manifest > /tmp/p0f.log 2>&1; echo "exit=$?"`
Expected: `exit=1`, `ImportError` for `scripts.tutorial.shoot`.

- [ ] **Step 3: Write the manifest**

`scripts/tutorial/shots.json` — the two Phase-0 proof shots; later phases append entries in their own tasks:

```json
{
  "base_url": "http://127.0.0.1:8010",
  "viewports": {
    "desktop": { "width": 1440, "height": 900 },
    "phone": { "width": 390, "height": 844 }
  },
  "roles": {
    "owner": { "username": "demo.owner" },
    "cashier": { "username": "demo.rep" }
  },
  "shots": [
    {
      "id": "00-01-receive-dialog-desktop",
      "chapter": "00-engine-proof",
      "role": "owner",
      "viewport": "desktop",
      "recipe": ["people", "catalogue", "opening"],
      "steps": [
        { "action": "goto", "path": "/products/" },
        { "action": "wait_for", "selector": "#modal_root" },
        { "action": "click", "selector": "button:has-text(\"Receive Delivery\")" },
        { "action": "wait_for", "selector": "#modal_root [role=\"dialog\"]" }
      ],
      "target": null,
      "full_page": false
    },
    {
      "id": "00-02-receive-dialog-phone",
      "chapter": "00-engine-proof",
      "role": "owner",
      "viewport": "phone",
      "recipe": ["people", "catalogue", "opening"],
      "steps": [
        { "action": "goto", "path": "/products/" },
        { "action": "click", "selector": "button#menu-toggle" },
        { "action": "wait_for", "selector": "#mobile-menu:not(.hidden)" },
        { "action": "click", "selector": "#mobile-menu a[href=\"/products/\"]" },
        { "action": "click", "selector": "button:has-text(\"Receive Delivery\")" },
        { "action": "wait_for", "selector": "#modal_root [role=\"dialog\"]" }
      ],
      "target": null,
      "full_page": false
    }
  ]
}
```

**The drawer selectors are verified, not guessed.** `templates/partials/header.html:149` is the trigger (`button#menu-toggle`, `aria-controls="mobile-menu"`) and `:162` is the drawer (`div#mobile-menu`), and it is plain JavaScript, not Alpine: `templates/_base.html:135-144` toggles the Tailwind `hidden` class on the drawer and swaps `#menu-icon-open`/`#menu-icon-close`. So open it with a real click and prove it opened with `#mobile-menu:not(.hidden)`; a `wait_for` on bare `#mobile-menu` would pass while the drawer is still closed.

Scope every drawer click to `#mobile-menu` — that is what `#mobile-menu a[href="/products/"]` does here. The page contains a second `a[href="/products/"]` in the desktop nav (`templates/partials/header.html:41`), and at 390 px that one is `display: none`. `page.click()` is non-strict and takes the first match, so an unscoped selector waits forever on the hidden desktop link. Any later chapter that shoots the drawer (Tasks 13 and 18) uses the same scoped form; `core/templates/core/partials/nav.html` also carries `id="mobile-menu"` but no template includes it, so the page really has one drawer.

- [ ] **Step 4: Write the harness**

`scripts/tutorial/shoot.py`:

```python
"""Replay shots.json through Playwright and write the PNGs the manual is made of.

Two browser contexts hold the owner and cashier cookies, which is what makes a
role-refusal screenshot honest: the cashier really is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.tutorial.isolation import assert_isolated

ACTIONS = {"goto", "click", "fill", "press", "wait_for", "evaluate"}
REPO = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO / "docs" / "onboarding"
SHOTLOG = OUT_ROOT / "SHOTLOG.md"


def load_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> list[str]:
    problems = []
    seen = set()
    for shot in manifest["shots"]:
        if shot["id"] in seen:
            problems.append(f"duplicate shot id {shot['id']}")
        seen.add(shot["id"])
        if shot["role"] not in manifest["roles"]:
            problems.append(f"{shot['id']}: unknown role {shot['role']!r}")
        if shot["viewport"] not in manifest["viewports"]:
            problems.append(f"{shot['id']}: unknown viewport {shot['viewport']!r}")
        for step in shot["steps"]:
            if step["action"] not in ACTIONS:
                problems.append(f"{shot['id']}: unknown action {step['action']!r}")
    return problems


def png_path(manifest: dict, shot: dict) -> Path:
    return OUT_ROOT / "img" / shot["chapter"] / f"{shot['id']}.png"


def shotlog_row(shot: dict, png: str, captured: str) -> str:
    route = next((s["path"] for s in shot["steps"] if s["action"] == "goto"), "")
    return (
        f"| `{shot['id']}` | {png} | {route or '—'} | {shot['role']} | "
        f"{shot['viewport']} | {', '.join(shot['recipe'])} | {captured} |"
    )


def _login(page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/login/", wait_until="networkidle")
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")


def _pages(browser, manifest: dict):
    """One persistent context per role: this is what makes a refusal frame honest."""
    from scripts.tutorial.seed_demo import DEMO_PASSWORD

    pages = {}
    for role, spec in manifest["roles"].items():
        context = browser.new_context()
        page = context.new_page()
        _login(page, manifest["base_url"], spec["username"], DEMO_PASSWORD)
        if "/login/" in page.url:
            raise RuntimeError(f"{role} could not sign in at {manifest['base_url']}")
        pages[role] = (context, page)
    return pages


def capture(manifest: dict, shot: dict, page, viewport: dict) -> Path:
    page.set_viewport_size(viewport)
    for step in shot["steps"]:
        action = step["action"]
        if action == "goto":
            page.goto(manifest["base_url"] + step["path"], wait_until="networkidle")
        elif action == "click":
            page.click(step["selector"])
            page.wait_for_load_state("networkidle")
        elif action == "fill":
            page.fill(step["selector"], step["value"])
            if step.get("then_wait"):
                page.wait_for_selector(step["then_wait"])
        elif action == "press":
            page.keyboard.press(step["key"])
        elif action == "wait_for":
            page.wait_for_selector(step["selector"], timeout=15000)
        elif action == "evaluate":
            page.evaluate(step["script"])
    path = png_path(manifest, shot)
    path.parent.mkdir(parents=True, exist_ok=True)
    if shot.get("target"):
        page.locator(shot["target"]).screenshot(path=str(path))
    else:
        page.screenshot(path=str(path), full_page=bool(shot.get("full_page")))
    return path


def _append_shotlog(rows: list[str]) -> None:
    header = (
        "| Shot | Image | Route | Role | Viewport | Recipe | Captured |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    existing = SHOTLOG.read_text(encoding="utf-8") if SHOTLOG.exists() else ""
    body = "\n".join(row for row in existing.splitlines() if not row.startswith("| `"))
    SHOTLOG.write_text(f"# Shot log\n\n{header}{body}\n" + "\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--manifest", default=str(Path(__file__).with_name("shots.json")))
    args = parser.parse_args(argv)

    from scripts.tutorial.seed_demo import _guard, run as run_recipes

    _guard()  # refuses before Django is set up, then asserts the resolved settings
    from django.conf import settings

    manifest = load_manifest(Path(args.manifest))
    assert_isolated(settings, base_url=manifest["base_url"])
    problems = validate_manifest(manifest)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1

    selected = [s for s in manifest["shots"] if _matches(s, args.chapter)]
    names: list[str] = []
    for shot in selected:
        for recipe in shot["recipe"]:
            if recipe not in names:
                names.append(recipe)
    run_recipes(names)

    from playwright.sync_api import sync_playwright

    rows = []
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        pages = _pages(browser, manifest)
        try:
            for shot in selected:
                _, page = pages[shot["role"]]
                path = capture(manifest, shot, page, manifest["viewports"][shot["viewport"]])
                rows.append(
                    shotlog_row(
                        shot,
                        path.relative_to(OUT_ROOT).as_posix(),
                        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )
                )
                print(f"shot {shot['id']} -> {path}")
        finally:
            for context, _ in pages.values():
                context.close()
            browser.close()
    _append_shotlog(rows)
    return 0


def _matches(shot: dict, chapter: str) -> bool:
    return chapter == "all" or shot["chapter"].startswith(chapter)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Two invariants this file has to keep, because they are how a chapter lies: the guard runs **before** `_pages()` opens a browser, and `run_recipes()` receives the recipe names in the order the shots list them (`people` before anything that signs in as those people). `assert_isolated(settings, base_url=manifest["base_url"])` is what makes Task 8 Step 1's edited-manifest test refuse rather than capture.

- [ ] **Step 5: Run the tests to green**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0g.log 2>&1; echo "exit=$?"`
Expected: `exit=0`. These tests never open a browser — they read and validate the committed manifest.

- [ ] **Step 6: Capture the two proof shots**

With the launcher from Task 2 running:

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.seed_demo --reset people catalogue opening`
Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.shoot --chapter 00`
Expected: two lines `shot 00-01-receive-dialog-desktop -> ...`, `shot 00-02-...`, and `docs/onboarding/img/00-engine-proof/` holding two PNGs. (`shoot.py` seeds the union of its own shots' recipes, so the first command is optional — run it anyway, and confirm the second does not re-create the accounts it is about to sign in as.)

- [ ] **Step 7: Look at them**

Open both PNGs. The desktop frame must show the Receive Delivery dialog **over** the products ledger with the ledger still visible behind it, and the phone frame must show the same dialog at 390 px without horizontal clipping. If the dialog is missing, the htmx swap was not waited for — that is the harness's core risk and Phase 0 does not exit until both frames are real.

- [ ] **Step 8: Commit**

```bash
git add scripts/tutorial/shoot.py scripts/tutorial/shots.json \
        scripts/tutorial/tests/test_shoot_manifest.py \
        docs/onboarding/SHOTLOG.md docs/onboarding/img/00-engine-proof
git commit -m "Capture the delivery dialog over the ledger at both viewports"
```

### Task 7: The four verification gates

**Files:**
- Create: `scripts/tutorial/verify.py`
- Test: `scripts/tutorial/tests/test_verify_gates.py`

**Interfaces:**
- Consumes: `authapp.urls`, `core.urls`, `docs/onboarding/*.md`, `shots.json`, `SHOTLOG.md`, `img/**`.
- Produces: `all_route_patterns() -> set[str]`, `spec_route_count(spec_path) -> int`, `matrix_routes(spec_path) -> set[str]`, `_matrix_problems(patterns, matrix) -> list[str]`, `gate_route_matrix(spec_path) -> list[str]`, `normalize(path) -> str`, `gate_images_on(chapter_files, root) -> list[str]`, `gate_images(chapters_dir) -> list[str]`, `gate_paths(chapters_dir) -> list[str]`, `gate_shotlog(chapters_dir, manifest_path) -> list[str]`, `PLACEHOLDER_LOOKUPS: dict[str, Callable[[], str]]`, `main() -> int`.

- [ ] **Step 1: Write the failing tests**

`scripts/tutorial/tests/test_verify_gates.py`:

```python
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from scripts.tutorial import verify

SPEC = Path("docs/superpowers/specs/2026-11-03-onboarding-tutorial-design.md")


class RouteMatrixGateTests(SimpleTestCase):
    def test_the_urlconf_resolves_to_the_count_the_spec_claims(self):
        self.assertEqual(len(verify.all_route_patterns()), verify.spec_route_count(SPEC))

    def test_a_spec_that_stops_naming_its_count_is_itself_a_failure(self):
        with self.assertRaisesRegex(AssertionError, "no longer states"):
            verify.spec_route_count(Path(__file__))

    def test_the_committed_spec_matrix_covers_every_route(self):
        self.assertEqual(verify.gate_route_matrix(SPEC), [])

    def test_a_route_the_matrix_omits_is_reported(self):
        real = {"products/receipts/receive/"}
        self.assertIn(
            "route missing from the coverage matrix",
            " ".join(verify._matrix_problems(real, set())),
        )

    def test_a_matrix_row_the_urlconf_does_not_have_is_reported(self):
        documented = {"/accounts/<id>/reset-password/"}
        self.assertIn(
            "matrix lists a route the URLconf does not have",
            " ".join(verify._matrix_problems({"accounts/"}, documented)),
        )

    def test_placeholder_names_do_not_have_to_agree(self):
        self.assertEqual(
            verify.normalize("products/<uuid:product_id>/update-stocks"),
            verify.normalize("/products/<id>/update-stocks"),
        )


class ImageGateTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "img" / "01-x").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _chapter(self, name: str, body: str) -> Path:
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_chapter_that_points_at_no_file_fails(self):
        chapter = self._chapter("01-x.md", "![x](img/01-x/01-missing.png)\n")
        problems = verify.gate_images_on([chapter], root=self.tmp)
        self.assertIn("missing image", " ".join(problems))

    def test_a_png_that_no_chapter_references_fails(self):
        self._chapter("01-x.md", "![x](img/01-x/01-real.png)\n")
        (self.tmp / "img" / "01-x" / "01-real.png").write_bytes(b"\x89PNG")
        (self.tmp / "img" / "01-x" / "02-orphan.png").write_bytes(b"\x89PNG")

        self.assertIn("orphan image", " ".join(verify.gate_images(self.tmp)))

    def test_a_referenced_png_present_on_disk_passes(self):
        chapter = self._chapter("01-x.md", "![x](img/01-x/01-real.png)\n")
        (self.tmp / "img" / "01-x" / "01-real.png").write_bytes(b"\x89PNG")

        self.assertEqual(verify.gate_images(self.tmp), [])


class PathGateTests(SimpleTestCase):
    def test_a_typo_in_a_prose_path_is_caught(self):
        self.assertIn("does not resolve", " ".join(verify._path_problems(["/orders/nope/"])))

    def test_the_misspelled_batch_print_route_is_a_real_route(self):
        self.assertEqual(verify._path_problems(["/orders/checks-orders/{day}/{users}/print"]), [])

    def test_placeholders_are_named_in_the_lookup_table(self):
        self.assertIn("{order_id}", verify.PLACEHOLDER_LOOKUPS)
```

- [ ] **Step 2: Run to watch them fail**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial.tests.test_verify_gates > /tmp/p0h.log 2>&1; echo "exit=$?"`
Expected: `exit=1`, `ImportError` for `scripts.tutorial.verify`.

- [ ] **Step 3: Write the gates**

`scripts/tutorial/verify.py`:

```python
"""The four gates that let this manual claim nothing was skipped.

Run after every chapter and at the close of every phase:
    DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.verify
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from django.utils import timezone

REPO = Path(__file__).resolve().parents[2]
CHAPTERS = REPO / "docs" / "onboarding"
SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-11-03-onboarding-tutorial-design.md"
IMAGE_RE = re.compile(r"!\[[^\]]*\]\((img/[^)]+)\)")
PATH_RE = re.compile(r"`(/[A-Za-z0-9_\-./{}?=&%]*)`")
MATRIX_ROW_RE = re.compile(r"^\|\s*`?(/[^\s|`]*)`?\s*\|")
COUNT_RE = re.compile(r"\*\*(\d+)\*\* app routes")

PLACEHOLDER_LOOKUPS = {
    "{order_id}": lambda: str(_row("core.Order", "id")),
    "{order_code}": lambda: str(_row("core.Order", "code")),
    "{order_number}": lambda: "1",
    "{product_id}": lambda: str(_row("core.Product", "id")),
    "{batch_id}": lambda: str(_row("core.StockBatch", "id")),
    "{receipt_id}": lambda: str(_row("core.StockReceipt", "id")),
    "{draft_id}": lambda: str(_row("core.StockReceiptDraft", "id")),
    "{account_id}": lambda: str(_row("authapp.Account", "id")),
    "{task_id}": lambda: "00000000-0000-0000-0000-000000000000",
    "{day}": lambda: f"{timezone.localdate():%Y-%m-%d}",
    "{users}": lambda: "all",
}


def _row(model_label: str, field: str):
    from django.apps import apps

    model = apps.get_model(model_label)
    return model.objects.order_by("?").values_list(field, flat=True).first()


def all_route_patterns() -> set[str]:
    """Full app routes, prefixes included: 11 from authapp, 43 from core.

    The walk accumulates the `products/` and `orders/` prefixes that core/urls.py
    declares through include([...]) — without it the matrix rows, which are written
    as people see them (/products/receipts/receive/), could never match.
    """
    from importlib import import_module

    from django.urls.resolvers import URLPattern, URLResolver

    found = set()

    def walk(patterns, prefix):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns, prefix + str(entry.pattern))
            elif isinstance(entry, URLPattern):
                found.add(prefix + str(entry.pattern))

    for module in ("authapp.urls", "core.urls"):
        walk(import_module(module).urlpatterns, "")
    return found


def spec_route_count(spec_path: Path = SPEC) -> int:
    """The route count the spec claims, read from its own sentence.

    The tripwire has to live somewhere, and hard-coding 54 in a test would make the
    gate go red every time the other lane lands a route — which is the one event the
    gate exists to notice. Parsing the spec keeps one source of truth: change the
    number there, and the matrix gate demands the row that goes with it.
    """
    match = COUNT_RE.search(Path(spec_path).read_text(encoding="utf-8"))
    if not match:
        raise AssertionError(
            f"{spec_path} no longer states its count as '**N** app routes' — "
            "keep that phrasing, or the gate stops counting anything"
        )
    return int(match.group(1))


def matrix_routes(spec_path: Path) -> set[str]:
    routes = set()
    for line in Path(spec_path).read_text(encoding="utf-8").splitlines():
        match = MATRIX_ROW_RE.match(line.strip())
        if match:
            routes.add(match.group(1))
    return routes


def _matrix_problems(patterns: set[str], matrix: set[str]) -> list[str]:
    """Both directions, because a matrix can lie by omission and by invention."""
    problems = [
        f"route missing from the coverage matrix: {m}"
        for m in sorted(patterns - matrix)
    ]
    problems += [
        f"matrix lists a route the URLconf does not have: {m}"
        for m in sorted(matrix - patterns)
    ]
    return problems


def gate_route_matrix(spec_path: Path = SPEC) -> list[str]:
    """Every URLconf route must appear as a row in the spec's matrix, and vice versa."""
    documented = {normalize(p) for p in matrix_routes(spec_path)}
    real = {normalize(p) for p in all_route_patterns()}
    return _matrix_problems(real, documented)


def normalize(path: str) -> str:
    """`products/<uuid:product_id>/update-stocks` and
    `/products/{product_id}/update-stocks` and `/products/<id>/update-stocks` all
    become /products/{_}/update-stocks.

    Placeholder *names* are deliberately erased: the URLconf calls it product_id, the
    spec's prose calls it <id>, and making those agree by hand is how a coverage gate
    gets weakened until it passes. The shape is what must match.
    """
    path = path.strip().lstrip("/").rstrip("$").lstrip("^")
    path = re.sub(r"\(\?P<([a-z_]+)>[^)]*\)", "{_}", path)
    path = re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", "{_}", path)
    path = re.sub(r"\{[^}]*\}", "{_}", path)
    return "/" + path.strip("/")


def gate_images_on(chapter_files: list[Path], root: Path = CHAPTERS) -> list[str]:
    problems = []
    for chapter in chapter_files:
        for match in IMAGE_RE.finditer(Path(chapter).read_text(encoding="utf-8")):
            if not (root / match.group(1)).is_file():
                problems.append(f"missing image {match.group(1)} referenced by {chapter.name}")
    return problems


def gate_images(chapters_dir: Path = CHAPTERS) -> list[str]:
    chapter_files = list(chapters_dir.glob("[0-9][0-9]-*.md"))
    problems = gate_images_on(chapter_files, chapters_dir)
    referenced = {
        match.group(1)
        for chapter in chapter_files
        for match in IMAGE_RE.finditer(Path(chapter).read_text(encoding="utf-8"))
    }
    for png in chapters_dir.glob("img/**/*.png"):
        relative = png.relative_to(chapters_dir).as_posix()
        if relative not in referenced:
            problems.append(f"orphan image {relative}")
    return problems


def _path_problems(paths: list[str]) -> list[str]:
    from django.urls import resolve
    from django.urls.exceptions import Resolver404

    problems = []
    for path in paths:
        concrete = fill_placeholders(path)
        if concrete is None:
            problems.append(f"unknown placeholder in `{path}`")
            continue
        try:
            resolve(concrete.split("?")[0])
        except Resolver404:
            problems.append(f"`{path}` does not resolve to a view")
    return problems


def fill_placeholders(path: str) -> str | None:
    out = path
    for token, lookup in PLACEHOLDER_LOOKUPS.items():
        if token in out:
            value = lookup()
            if value is None:
                return None
            out = out.replace(token, str(value))
    return out


def gate_paths(chapters_dir: Path = CHAPTERS) -> list[str]:
    paths = {
        match.group(1)
        for chapter in chapters_dir.glob("[0-9][0-9]-*.md")
        for match in PATH_RE.finditer(Path(chapter).read_text(encoding="utf-8"))
    }
    return _path_problems(sorted(paths))


def gate_shotlog(chapters_dir: Path = CHAPTERS, manifest_path: Path | None = None) -> list[str]:
    manifest = json.loads(
        (manifest_path or Path(__file__).with_name("shots.json")).read_text(encoding="utf-8")
    )
    log = (chapters_dir / "SHOTLOG.md").read_text(encoding="utf-8") if (chapters_dir / "SHOTLOG.md").exists() else ""
    problems = []
    for shot in manifest["shots"]:
        png = chapters_dir / "img" / shot["chapter"] / f"{shot['id']}.png"
        if not png.is_file():
            problems.append(f"shot {shot['id']} has no PNG")
        if f"`{shot['id']}`" not in log:
            problems.append(f"shot {shot['id']} has no SHOTLOG row")
    for png in chapters_dir.glob("img/**/*.png"):
        if png.stem.strip("`") not in {s["id"] for s in manifest["shots"]}:
            problems.append(f"{png.name} was not produced by any manifest shot")
    return problems


def main() -> int:
    from scripts.tutorial.seed_demo import _guard

    _guard()
    failures = (
        gate_route_matrix()
        + gate_images()
        + gate_paths()
        + gate_shotlog()
    )
    if failures:
        print(f"verify: {len(failures)} problem(s)", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("verify: all gates green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Two details to settle while writing, not later: `normalize()` must be tested against the real URLconf before `gate_route_matrix` is trusted (run it in a shell and print both sets — the `<uuid:...>` and `(?P<...>` forms must collapse to the same token names, and where they do not, extend `PLACEHOLDER_LOOKUPS` rather than special-casing the regex); and the `00-engine-proof` chapter folder is excluded by the `[0-9][0-9]-*.md` glob, so Phase 0's proof shots are checked by `gate_shotlog` but not by `gate_images`.

- [ ] **Step 4: Run to green**

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p0i.log 2>&1; echo "exit=$?"`
Expected: `exit=0`. If `test_the_urlconf_has_the_number_of_routes_the_spec_counts` fails, the tree moved: re-run the counting walk, correct the spec's 54/59 and this test together, add or drop the matrix row that moved, and say so in the commit message. Never lower the number to make a gate pass — the gate exists to make the manual's "nothing skipped" claim true.

- [ ] **Step 5: Run the CLI**

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.verify`
Expected: `verify: all gates green` (at Phase 0 there are no numbered chapters yet, so the image and path gates have nothing to fail on — that is correct, not vacuous, and Task 8 gives them something to bite on).

- [ ] **Step 6: Commit**

```bash
git add scripts/tutorial/verify.py scripts/tutorial/tests/test_verify_gates.py
git commit -m "Add the four gates that prove the manual skipped nothing"
```

### Task 8: Phase 0 exit — the matrix filled and the engine proven

**Files:**
- Modify: `docs/superpowers/specs/2026-11-03-onboarding-tutorial-design.md` (only if a count moved)
- Create: `docs/onboarding/README.md` (replace the stub's engine paragraph)

- [ ] **Step 1: Prove the guard chain end to end**

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.shoot --chapter 00 --manifest <(echo '{"base_url":"http://127.0.0.1:8000"}')` — Git Bash process substitution is not enough here; instead copy `shots.json` to `/tmp/evil.json`, change its `base_url` to `http://127.0.0.1:8000`, and run:
`DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.shoot --chapter 00 --manifest /tmp/evil.json`
Expected: `NotScratchInstall: ... base URL ... is not the scratch server on port 8010` and **no browser opens**. This is the single most important test in the plan; if it captures instead, the lane stops.

- [ ] **Step 2: Confirm both role jars work**

Add one temporary manifest shot with `"role": "cashier"` and `"steps": [{"action": "goto", "path": "/products/"}]`, shoot it, and confirm the PNG shows the login page — the honest picture of a cashier refused, which chapter 01 will reuse. Then delete the temporary entry.

- [ ] **Step 3: Fill the matrix**

Confirm `verify.gate_route_matrix()` returns `[]` — all 59 entries mapped, in both directions, including the `update-details` row this lane added in `8d716dd` and the `/help/` row that was missing when the spec was written. If the gate names `/help/`, add that row to the spec's matrix owned by chapter 02 (it is linked from the header, the mobile drawer and the hub, and needs no session) rather than editing the count down.

Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial.tests.test_verify_gates -v 2 > /tmp/p0j.log 2>&1; echo "exit=$?"`
Expected: `exit=0`

- [ ] **Step 4: Record the engine in the index**

Replace the stub's second paragraph in `docs/onboarding/README.md` with the working commands (`run_demo_server.ps1`, `seed_demo.py --reset`, `shoot.py --chapter`, `verify.py`) exactly as they proved out in Steps 1–3, and note the two proof PNGs under `img/00-engine-proof/` as throwaway, not manual content.

- [ ] **Step 5: Run the whole suite, then commit**

Run: `.venv/Scripts/python.exe manage.py test --keepdb > /tmp/p0k.log 2>&1; echo "exit=$?"`
Expected: `exit=0`. Stage explicit paths only.

```bash
git add docs/onboarding/README.md docs/superpowers/specs/2026-11-03-onboarding-tutorial-design.md \
        docs/superpowers/plans/2026-11-04-onboarding-tutorial.md
git commit -m "Prove the capture engine against the scratch install"
```

---

# Phase 1 — Getting in

Two chapters, the refusal and session-state recipes, and the first prose that has to survive `verify.py`. Exit: both chapters render clean, every claim re-verified, 8 matrix entries shot (chapter 01 owns 6 authapp routes, chapter 02 owns `/` and `/help/`).

### Task 9: The refusal and expired-session states

**Files:**
- Modify: `scripts/tutorial/seed_demo.py`
- Test: `scripts/tutorial/tests/test_seed_recipes.py`

**Interfaces:**
- Consumes: `people()`, Django's login machinery.
- Produces: `refusals() -> None` (a cashier who is signed in, so a role refusal can be photographed), and `ANONYMOUS_PATHS: list[str]` — the routes chapter 01 quotes.

- [ ] **Step 1: Write the failing test**

```python
class RefusalStateTests(TestCase):
    def test_a_signed_in_cashier_exists_for_the_refusal_shot(self):
        seed_demo.people()
        seed_demo.refusals()

        from django.contrib.auth import get_user_model

        cashier = get_user_model().objects.get(username=seed_demo.CASHIER_USERNAME)
        self.assertTrue(cashier.is_active)

    def test_the_anonymous_paths_are_all_real_routes(self):
        from scripts.tutorial import verify

        self.assertEqual(verify._path_problems(seed_demo.ANONYMOUS_PATHS), [])
```

- [ ] **Step 2: Run to watch it fail** — `AttributeError: no attribute 'refusals'`.

- [ ] **Step 3: Implement**

```python
ANONYMOUS_PATHS = ["/accounts/", "/products/", "/orders/?view=orders", "/orders/?view=reports"]


def refusals() -> None:
    """Nothing to build: the state is 'a cashier is signed in and clicks a link
    they cannot open'. The recipe exists so the manifest names it honestly."""
    _owner()
    from django.contrib.auth import get_user_model

    get_user_model().objects.get(username=CASHIER_USERNAME)
```

- [ ] **Step 4: Register `"refusals"` in `REGISTRY`.** The eleven-name assertion is a `>=` check (it moves to Task 21, where the eleventh recipe lands), so a twelfth entry is legal by construction — do not edit that test to make room, and do not drop `refusals` from `--list` either, because chapter 01's "Data that must already exist" line names the recipes a reader would re-run.

- [ ] **Step 5: Run to green, then commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Name the refusal state the sign-in chapter photographs"
```

### Task 10: Chapter 01 — Sign in, and your own account

**Files:**
- Create: `docs/onboarding/01-sign-in-and-your-account.md`
- Modify: `scripts/tutorial/shots.json`

**Interfaces:**
- Consumes: `_template.md`, shots `01-*`, recipes `people`, `refusals`.
- Produces: chapter file with the five blocks; the matrix rows for `/login/`, `/login_success/`, `/logout`, `/profile/`, `/password/change/`, `/password/change/done/` become *captured* as well as mapped.

- [ ] **Step 1: Re-verify the six claims this chapter makes**

Open each file and confirm the string still reads as quoted; correct the chapter, not the claim:

| Claim | Where to read it |
|---|---|
| Three validation messages: empty username, empty password, wrong credentials | `authapp/views.py` `signin()` — the `validations` dict keys and their literal messages |
| A role refusal and a dead session look identical | `utils.py` / `LOGIN_URL` in settings, plus `signin()` discarding `?next` |
| The profile page carries a 10-digit phone note | `authapp/templates/authapp/profile.html`, and `authapp/models.py:9` `max_length=10` |
| Change-password runs the project validators | `myshopproject/settings.py` `AUTH_PASSWORD_VALIDATORS` |
| The logout route has no trailing slash | `authapp/urls.py:41` |
| No password reset email exists anywhere | `grep -rn "EMAIL_" myshopproject/settings.py` → nothing |

- [ ] **Step 2: Add the manifest entries**

```json
{
  "id": "01-01-login-empty-username",
  "chapter": "01-sign-in-and-your-account",
  "role": "owner",
  "viewport": "desktop",
  "recipe": ["people", "refusals"],
  "steps": [
    { "action": "goto", "path": "/login/" },
    { "action": "fill", "selector": "input[name='password']", "value": "wrong-on-purpose" },
    { "action": "click", "selector": "button[type='submit']" },
    { "action": "wait_for", "selector": "[role='alert'], .text-rose-600" }
  ],
  "target": "form",
  "full_page": false
}
```

Add the sibling entries the same way, each with its own `id`: `01-02-login-empty-password`, `01-03-login-wrong-credentials`, `01-04-role-refusal-lands-on-login` (cashier jar, `goto /products/`), `01-05-profile`, `01-06-password-change`, `01-07-password-change-done`. Seven shots, matching the phase's "7 matrix entries".

- [ ] **Step 3: Shoot and look**

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.shoot --chapter 01`
Expected: 7 PNGs. Open `01-04`: it must be the login page reached *while signed in as the cashier*. If it shows the hub or a products table instead, the shot was taken with the wrong jar (the owner's) — the frame is a lie about the role gate, so fix the recipe's `role` before writing any prose about it.

- [ ] **Step 4: Write the prose**

Copy `_template.md`. Content requirements, all of which the shots must carry:
- "What this is for": signing in, and the three things you can change about yourself.
- "You need": both roles; the username the owner gave you; that no email reset exists, so a forgotten password is a walk to the owner.
- "Steps": one numbered step per PNG, in the order captured.
- "When it goes wrong": quote each of the three `signin()` messages verbatim; then the paragraph the spec requires — "no, you can't see that" and "your session ended" are the same screen, and `?next` is discarded so you land on the plain login form.
- "Notes & limits": barcode scanners are not integrated; the login card can appear *inside* a table when an htmx partial outlives the session (link the PNG if you captured one, otherwise state it in words and cross-reference chapter 13).

- [ ] **Step 5: Green the gates, then commit**

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.verify` → `verify: all gates green`
Run: `.venv/Scripts/python.exe manage.py test --keepdb scripts.tutorial > /tmp/p1a.log 2>&1; echo "exit=$?"` → `exit=0`

```bash
git add docs/onboarding/01-sign-in-and-your-account.md docs/onboarding/img/01-sign-in-and-your-account \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json
git commit -m "Write the sign-in chapter from captured screens"
```

### Task 11: Chapter 02 — The owner's hub

Same shape as Task 10; the specifics:

- [ ] **Step 1: Re-verify** — `core/views.py` `base`/hub view and its role branch (the spec cites `core/views.py:113-120` — re-read it, it moves), the hub card template, `F2`'s handler, the theme toggle, the two cards the spec calls mislabelled ("Download CSV" navigates instead of downloading; find the actual `href`), and `core/views.py:114` `help_support` — confirm it carries neither `@login_required` nor `@user_passes_test`, and read `core/templates/core/help.html` for what it actually offers (the redesign left its contact line undecided, so quote what is on the page, not what was intended).
- [ ] **Step 2: Manifest** — `02-01-hub-desktop`, `02-02-hub-phone-drawer`, `02-03-card-destinations`, `02-04-snapshot-tiles`, `02-05-f2-lands-on-register`, `02-06-theme-dark`, `02-07-mislabelled-cards`, `02-08-help-page` (8 shots, all `owner`).
- [ ] **Step 3: Shoot and look** — the phone frame must show the drawer open, which means `button#menu-toggle` clicked and `#mobile-menu:not(.hidden)` waited for, with every drawer link addressed as `#mobile-menu a[...]` (see Task 6 Step 3 for why the unscoped href matches the hidden desktop nav first). `02-08` must be reached by clicking the header link, not by `goto`, so the frame proves the route is one a person can actually find.
- [ ] **Step 4: Prose** — "When it goes wrong" carries the duplicate/mislabelled buttons as named-at-the-moment promises, not a chapter-13 note. "Notes & limits" states that `/help/` opens without signing in — the only screen in the manual that does — and what its contact line does and does not do.
- [ ] **Step 5: `verify.py` green, suite green, commit**

```bash
git add docs/onboarding/02-the-owners-hub.md docs/onboarding/img/02-the-owners-hub \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json
git commit -m "Write the owner's hub chapter from captured screens"
```

---

# Phase 2 — Stocking the shop

Exit: the import captured *live* (bar off zero), not described; 11 matrix entries shot. This phase is the first one that can fail on infrastructure: the worker must consume from the scratch install.

### Task 12: Prove the tutorial queue is the only thing the demo worker eats

**Files:**
- Modify: `scripts/tutorial/run_demo_server.ps1` (worker already `-Q tutorial`), `scripts/tutorial/seed_demo.py`

**Interfaces:**
- Consumes: `core.tasks.import_products_task`, `CELERY_TASK_DEFAULT_QUEUE`.
- Produces: `import_recipe_csv() -> Path` writing the CSV the import task consumes, and the `import` recipe.

- [ ] **Step 1: Write the failing test**

```python
class ImportRecipeTests(TestCase):
    def test_the_csv_uses_the_column_contract_the_parser_reads(self):
        path = seed_demo.import_recipe_csv()

        header = path.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            [c.strip() for c in header.split(",")],
            ["PRODUCT", "SKU", "COST PRICE", "SELLING PRICE", "QUANTITY", "CATEGORY"],
        )

    def test_the_recipe_queues_a_task_on_the_tutorial_queue(self):
        from unittest.mock import patch

        seed_demo.catalogue()
        with patch("core.tasks.import_products_task.delay") as delay:
            seed_demo.import_recipe()

        self.assertTrue(delay.called)
```

- [ ] **Step 2: Run to watch it fail**, then implement `import_recipe_csv()` (write into `docs/onboarding/samples/` so the CSV the reader downloads is the CSV that was imported) and `import_recipe()` (read the file, call the task, poll `AsyncResult` until it is `SUCCESS`, then assert the products exist).

- [ ] **Step 3: Prove isolation at runtime, not in a mock**

With the launcher running and the shop's own worker also running:

Run: `.venv/Scripts/python.exe manage.py shell --settings=scripts.tutorial.demo_settings -c "from scripts.tutorial import seed_demo; seed_demo.import_recipe()"`
Then read `%LOCALAPPDATA%\myshop-tutorial\worker.log`.
Expected: the task appears in the **tutorial** worker's log and NOT in the shop's worker log (`Get-Content $env:LOCALAPPDATA\myshop\worker.log -Tail 20`). If the shop's worker ate it, stop: the queue override did not take, and no further recipe is safe to run.

- [ ] **Step 4: Run to green, commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py docs/onboarding/samples
git commit -m "Import a real CSV through the tutorial queue"
```

### Task 13: Chapter 03 — Bring the catalogue in

- [ ] **Step 1: Re-verify** — `/products/import-products/` + `/do` + `/track_progress/<task_id>` in `core/urls.py`, the client-side column contract text in the import dialog template, the "Auto-gen SKU" behaviour and category prefix rules in `core/forms.py`, the `Remove current image` checkbox condition, and `PROFIT_RATE_MAX`.
- [ ] **Step 2: Manifest** — `03-01-import-dialog`, `03-02-column-contract-error`, `03-03-progress-bar-live`, `03-04-import-complete`, `03-05-add-single-product`, `03-06-auto-generated-sku`, `03-07-photo-widget-with-image`, `03-08-photo-widget-without`, `03-09-monogram-row` (9 shots).
  `03-03` is the phase's exit proof: its steps must `fill` the file input (`{"action":"evaluate","script":"..."}` with `setInputFiles` on the page object is the Playwright way — add a `set_files` action to `shoot.py` `ACTIONS` and its validator, with a test in `test_shoot_manifest.py`), and the PNG must show a bar **above 0%**. If it shows 0%, the worker is down or the queue is wrong; go back to Task 12 Step 3.
- [ ] **Step 3: Shoot and look** — as above, plus the monogram row must be a product with no `image`.
- [ ] **Step 4: Prose** — "Notes & limits" states the absences the spec names: no import preview, no column mapper, no category or supplier master screens (category is a five-value enum, supplier is free text on a receipt).
- [ ] **Step 5: Gates green, suite green, commit**

```bash
git add docs/onboarding/03-bring-the-catalogue-in.md docs/onboarding/img/03-bring-the-catalogue-in \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json scripts/tutorial/shoot.py \
        scripts/tutorial/tests/test_shoot_manifest.py
git commit -m "Capture a live catalogue import for the stocking chapter"
```

### Task 14: The ledger-filter and removal recipes

- [ ] **Step 1: Failing tests**

```python
class RemovalRecipeTests(TestCase):
    def test_makes_throwable_products_and_one_protected_product(self):
        from core.models import Product

        seed_demo.catalogue()
        throwaway, protected = seed_demo.removal()

        self.assertEqual(Product.objects.filter(sku__startswith="DEMO-REMOVE").count(), throwaway)
        self.assertTrue(protected.stock > 0)


class LedgerFilterTests(TestCase):
    def test_the_catalogue_spans_every_filter_state(self):
        from django.db.models import BooleanField, ExpressionWrapper, F

        from core.models import Product

        seed_demo.catalogue()
        seed_demo.opening()

        self.assertTrue(Product.objects.filter(stock=0).exists(), "no depleted row")
        at_or_below = Product.objects.annotate(
            is_low=ExpressionWrapper(
                F("stock") <= F("low_stock_threshold"), output_field=BooleanField()
            )
        )
        self.assertTrue(at_or_below.filter(is_low=True).exclude(stock=0).exists(), "no low row")
        self.assertTrue(at_or_below.filter(is_low=False).exists(), "nothing above threshold")
```

The annotation lives in the test, not in `core` — it is the ledger's own low-stock comparison, and a helper added to production code to make a test read nicely is exactly the kind of change this lane is forbidden to make.

- [ ] **Step 2: Run to watch them fail**, then implement `removal()` (create six `DEMO-REMOVE-*` products at zero stock plus return one stocked product) and confirm `catalogue()` + `opening()` already satisfy the filter test; if not, adjust `CATALOGUE` thresholds and `opening()`'s quantities, not the test.
- [ ] **Step 3: Run to green, commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Seed throwaway products and every ledger filter state"
```

### Task 15: Chapter 04 — Read the Products & Stock ledger

- [ ] **Step 1: Re-verify** — `/products/summary/` tile formulas, the five status filters and five sorts in `core/views.py`/`core/tables.py`, the `Restock selected` button's visibility condition, the row action list, pagination at 25 (`core/batch_views.py:311` — re-read), and the `/` search shortcut.
- [ ] **Step 2: Manifest** — `04-01-ledger-default`, `04-02-valuation-tiles`, `04-03-filter-low`, `04-04-filter-depleted`, `04-05-restock-selected-button`, `04-06-sorted-by-price`, `04-07-row-actions-open`, `04-08-pager-page-2`, `04-09-search-with-slash` (9 shots; the phase total becomes 11 matrix entries counting 03's filter states).
- [ ] **Step 3: Shoot and look** — `04-05` must show the button existing only in the one filter state the code allows; if it never appears, the recipe has no selected rows and the shot is meaningless.
- [ ] **Step 4: Prose** — the empty states are part of the chapter, not an appendix: state what a fresh install with no products shows.
- [ ] **Step 5: Gates green, suite green, commit**

```bash
git add docs/onboarding/04-read-the-products-and-stock-ledger.md \
        docs/onboarding/img/04-read-the-products-and-stock-ledger \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json
git commit -m "Write the stock ledger chapter with every filter state captured"
```

---

# Phase 3 — Deliveries and counts

The biggest phase (17 entries) and the one most likely to surface a defect. Exit: the nine receipt routes shot in dialog context, and the out-of-balance lockout footer captured as paper, not paraphrased.

### Task 16: The `delivery` and `draft` recipes

**Interfaces:**
- Consumes: `receive_stock(..., lines=[ReceiptLine(product_id, quantity, unit_cost, selling_price)])`, `StockReceiptDraft`.
- Produces: `delivery() -> StockReceipt` (two supplier groups, multi-line, one line with a new selling price, one line whose cost rises above the shelf price) and `draft() -> StockReceiptDraft`.

- [ ] **Step 1: Failing tests**

```python
class DeliveryRecipeTests(TestCase):
    def test_one_line_carries_a_new_selling_price_that_lands_on_the_product(self):
        from core.models import Product

        seed_demo.catalogue()
        receipt = seed_demo.delivery()

        priced = receipt.batches.filter(price_applied__isnull=False).first()
        self.assertIsNotNone(priced, "no line booked a price change")
        priced.product.refresh_from_db()
        self.assertEqual(priced.product.price, priced.price_applied)
        self.assertNotEqual(priced.price_before, priced.price_applied)

    def test_two_supplier_groups_were_booked_as_two_receipts(self):
        from core.models import StockReceipt

        seed_demo.catalogue()
        seed_demo.delivery()

        self.assertGreaterEqual(StockReceipt.objects.filter(source="PURCHASE").count(), 2)
        self.assertTrue(
            {r.supplier_name for r in StockReceipt.objects.filter(source="PURCHASE")}
            - {""},
            "both receipts carry the same empty supplier",
        )

    def test_a_later_cost_change_makes_a_report_row_read_below_cost(self):
        seed_demo.catalogue()
        receipt = seed_demo.delivery()

        self.assertTrue(
            any(
                batch.unit_cost > batch.product.price
                for batch in receipt.batches.select_related("product")
            ),
            "nothing in the delivery is priced below its own cost",
        )


class DraftRecipeTests(TestCase):
    def test_the_draft_survives_for_the_continue_shot(self):
        from core.models import StockReceiptDraft

        seed_demo.catalogue()
        draft = seed_demo.draft()

        self.assertTrue(StockReceiptDraft.objects.filter(pk=draft.pk).exists())
        lines = draft.payload["groups"][0]["lines"]
        self.assertTrue(lines)
        self.assertEqual(
            sorted(lines[0]), ["product_id", "selling_price", "unit_cost", "units"]
        )

    def test_the_draft_is_still_unbooked(self):
        seed_demo.catalogue()
        draft = seed_demo.draft()

        self.assertIsNone(draft.booked_at)
        self.assertEqual(draft.receipts.count(), 0)
```

Verified against the tree, so these are contracts rather than guesses:

- A `StockReceipt` has **no** lines table. The per-line facts live on its `StockBatch` rows (`core/models.py:155-203`: `line_number`, `quantity_received`, `quantity_remaining`, `unit_cost`, `cost_is_estimated`, `price_before`, `price_applied`, reached as `receipt.batches`). So `delivery()` asserts against `receipt.batches`, and chapter 05's "this line changed a price" claim is only photographable because `price_before`/`price_applied` are real columns.
- A `StockReceiptDraft` keeps its rows in `payload`, a `JSONField` shaped by `_clean_draft_payload()` (`core/batch_views.py:956-1012`): `{"purchased_on": str, "groups": [{"supplier_name", "external_reference", "lines": [...]}]}` where every line is `{"product_id", "units", "unit_cost", "selling_price"}` and **every value is a string** — `units`, not `quantity`. `draft()` must write exactly that shape, because `Continue` restores what the autosave route stored, not what this recipe wished it had.
- `StockReceiptDraft.receipts` is the `related_name` of `StockReceipt.draft` (`on_delete=PROTECT`), which is why `wipe()` deletes receipts before drafts.
- [ ] **Step 3: Implement** — call `receive_stock()` twice with different `supplier_name` and `external_reference`, one line with `selling_price=Decimal("199.00")`, and build the draft with the same shape the autosave route writes.
- [ ] **Step 4: Run to green, commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Book a two-supplier delivery that also moves a selling price"
```

### Task 17: The `out-of-balance` and `after-hours` recipes

The `batches` recipe cannot exist yet — a partially sold and an emptied batch are both *consequences of selling*, which lands in Task 21 — so its two assertions live there. This task covers the two states the services refuse to produce, and nothing else.

- [ ] **Step 1: Failing tests**

```python
class OutOfBalanceTests(TestCase):
    def test_the_forced_drift_is_visible_and_bypasses_the_save_guard(self):
        from core.models import Product

        seed_demo.catalogue()
        seed_demo.opening()
        product = seed_demo.out_of_balance()

        product.refresh_from_db()
        self.assertNotEqual(
            product.stock,
            sum(batch.quantity_remaining for batch in product.batches.all()),
        )


class AfterHoursTests(TestCase):
    def test_the_sale_sits_outside_the_trading_window(self):
        from django.utils import timezone

        from core.models import Order

        seed_demo.catalogue()
        seed_demo.opening()
        order = seed_demo.after_hours()

        self.assertEqual(Order.objects.filter(pk=order.pk).count(), 1)
        hour = timezone.localtime(order.created).hour
        self.assertTrue(hour < 6 or hour >= 20, f"{hour} is inside 06:00-20:00")
```

- [ ] **Step 2: Run to watch them fail**, then implement with the sanctioned `QuerySet.update()` bypass only:

```python
def out_of_balance():
    """Deliberately break the invariant the shop's books must never break.

    QuerySet.update() skips Product.save(), which is the only reason this is
    possible at all — and the reason the capture lives on a scratch database.
    """
    from core.models import Product

    product = Product.objects.filter(stock__gt=0).order_by("name").first()
    Product.objects.filter(pk=product.pk).update(stock=product.stock + 7)
    product.refresh_from_db()
    return product


def after_hours():
    """One real sale, then its clock pushed outside 06:00-20:00.

    The shift needs QuerySet.update(): created is auto_now_add, so save() rewrites
    it back. This is the same sanctioned bypass as out_of_balance(), and for the same
    reason — the state is one the app produces by itself at 20:01 and refuses to
    produce on request.
    """
    import uuid
    from datetime import timedelta

    from django.utils import timezone

    from core.checkout import SaleLine, checkout
    from core.models import Order, Product

    product = Product.objects.filter(stock__gt=0).order_by("name").first()
    order = checkout(
        actor=_owner(),
        request_key=uuid.uuid4(),
        lines=[SaleLine(product.id, 1, product.price)],  # total_price, and the qty is 1
    )
    late = timezone.localtime() - timedelta(hours=timezone.localtime().hour + 3)
    Order.objects.filter(pk=order.pk).update(created=late)
    order.refresh_from_db()
    return order
```

Verified: `checkout(*, actor, request_key, lines) -> Order` (`core/checkout.py:73`) and `SaleLine.product_id/quantity/total_price` (`core/checkout.py:25-29`), so `after_hours()` gets an `Order` back and one quantity means the line total is the unit price. The `late` expression is deliberately an offset rather than `replace(hour=21)`: `TIME_ZONE` is `UTC` and Ghana is UTC+0, so a literal 21:30 works today but breaks the moment someone changes `TIME_ZONE` — and `timezone.localtime()` on an already-aware datetime must not be re-wrapped in `make_aware()`, which raises. If the shift ever lands back inside the window, the test's message says so.

- [ ] **Step 3: Run to green, commit**

```bash
git add scripts/tutorial/seed_demo.py scripts/tutorial/tests/test_seed_recipes.py
git commit -m "Force the two states the services refuse to produce"
```

### Task 18: Chapter 05 — Receive a delivery

- [ ] **Step 1: Re-verify** the nine `/products/receipts/…` routes, `?product_id=`, `?draft_id=`, `/receive/selected/`, the 700 ms draft autosave (`receive_stock.html:181` — re-read), the 413/409 refusals, the "blank means unchanged" line under the selling-price field, and the batch-restock refusal text for a product that is not at zero.
- [ ] **Step 2: Manifest** — `05-01-dialog-over-ledger`, `05-02-supplier-groups`, `05-03-invoice-reference`, `05-04-product-typeahead`, `05-05-unit-presets`, `05-06-selling-price-row`, `05-07-live-totals-warning`, `05-08-draft-row-in-ledger`, `05-09-continue-restores-typed-rows`, `05-10-refusal-kept-my-lines`, `05-11-booked-message`, `05-12-batch-restock-refusal`, `05-13-receipt-detail` (13 shots; the nine routes are covered by these plus `05-01`).
- [ ] **Step 3: Shoot and look** — `05-09` and `05-10` are the two that require a *failed* booking; drive them with an impossible quantity to trigger the refusal, and confirm the typed lines are still in the DOM in the PNG.
- [ ] **Step 4: Prose** — "When it goes wrong" quotes the 413 and 409 bands verbatim. "Notes & limits" states the price-before/price-applied trail is not rendered anywhere (the spec's Task 8 gap) and that supplier is free text with no master list.
- [ ] **Step 5: Gates green, suite green, commit**

```bash
git add docs/onboarding/05-receive-a-delivery.md docs/onboarding/img/05-receive-a-delivery \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json
git commit -m "Write the delivery chapter including its refusals"
```

### Task 19: Chapter 06 — Count and correct stock

- [ ] **Step 1: Re-verify** — `/products/stock/<id>/adjust/`, `/products/stock/<id>/batches/`, `POST /products/<id>/update-stocks`, the required Reason, the negative-correction refusal, the amber row pill, and the out-of-balance footer with its lockout wording (`core/inventory.py:181-192` `_assert_product_stock` and the template that renders the warning).
- [ ] **Step 2: Manifest** — `06-01-adjust-dialog`, `06-02-batch-radio-list`, `06-03-short-versus-found`, `06-04-reason-required`, `06-05-negative-correction-refusal`, `06-06-amber-pill`, `06-07-batch-history`, `06-08-out-of-balance-footer`, `06-09-lockout-blocks-receipt` (9 shots).
- [ ] **Step 3: Shoot and look** — `06-08` and `06-09` must come from the `out-of-balance` recipe, and the PNG must be the real footer. If the state cannot be reached, the recipe used `save()`; re-read Task 17.
- [ ] **Step 4: Prose** — the FIFO explanation is tied to the valuation number visible in `04-02`, and the chapter says plainly that stock is never typeable.
- [ ] **Step 5: Gates green, suite green, commit**

```bash
git add docs/onboarding/06-count-and-correct-stock.md docs/onboarding/img/06-count-and-correct-stock \
        docs/onboarding/SHOTLOG.md scripts/tutorial/shots.json
git commit -m "Capture the count lockout the inventory invariant produces"
```

### Task 20: Chapter 07 — Remove products

- [ ] **Step 1: Re-verify** — `/products/<id>/remove-product` + `/do`, `/products/remove-products/question` + `/do` + `/track_progress/<task_id>`, `remove_products_task`, and the mixed "removed N; M products were protected by stock or history" wording.
- [ ] **Step 2: Manifest** — `07-01-single-refusal`, `07-02-bulk-confirmation-six-names`, `07-03-removal-progress`, `07-04-mixed-result`, `07-05-gone-from-ledger` (5 shots).
- [ ] **Step 3: Shoot and look** — `07-03` needs the tutorial worker again.
- [ ] **Step 4: Prose** — state the missing deactivate toggle as an absence; the refusal in `07-01` is quoted, not summarised.
- [ ] **Step 5: Gates green, suite green, commit** — `git add` the chapter, its `img/`, `SHOTLOG.md`, `shots.json`; message `"Write the removal chapter with its protected-product refusal"`.

**Phase 3 review gate:** 17 entries shot, `verify.py` green, the full Django suite green, and the owner has read 05–07 rendered. Nothing in Phase 4 starts before that review.

---

# Phase 4 — Selling and paper

Exit: a real sale rung up on the scratch install, its receipt PDF in `samples/`, the after-hours missing button captured; 6 entries.

### Task 21: The `selling` recipe and the cashier cookie jar

**Files:**
- Modify: `scripts/tutorial/seed_demo.py` (add `selling()`, register it in `REGISTRY`)
- Test: `scripts/tutorial/tests/test_seed_recipes.py` (append `SellingRecipeTests`; its header already imports `get_user_model`, `TestCase` and `seed_demo`, so the new tests import `Order`, `OrderItem`, `timezone` and `timedelta` locally as shown)

**Interfaces:**
- Consumes: `people()`, `catalogue()`, `opening()`, `core.checkout.checkout`, `core.checkout.SaleLine`.
- Produces: `selling(below_cost: bool = False) -> None` and the registry name `"selling"`.

- [ ] **Step 1: Failing tests**

```python
class SellingRecipeTests(TestCase):
    def test_sales_land_on_two_cashiers_and_on_yesterday(self):
        from datetime import timedelta

        from django.utils import timezone

        from core.models import Order

        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.selling()

        today = timezone.localdate()
        self.assertEqual(Order.objects.filter(created__date=today).count(), 4)
        self.assertEqual(
            Order.objects.filter(created__date=today - timedelta(days=1)).count(), 2
        )
        self.assertTrue(
            Order.objects.filter(user__username=seed_demo.CASHIER_USERNAME).exists()
        )

    def test_one_sale_is_six_lines_so_the_receipt_is_tall(self):
        from django.db.models import Count

        from core.models import OrderItem

        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.selling()

        tallest = (
            OrderItem.objects.values("order").annotate(n=Count("id")).order_by("-n").first()
        )
        self.assertGreaterEqual(tallest["n"], 6)

    def test_one_line_was_sold_below_its_batch_cost(self):
        """The rose negative-profit row in chapter 11 is only honest if the frozen
        FIFO cost really exceeds what the customer paid."""
        from django.db.models import F

        from core.models import OrderItem

        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.delivery()
        seed_demo.selling(below_cost=True)

        self.assertTrue(
            OrderItem.objects.filter(cost_amount__gt=F("paid_amount")).exists(),
            "nothing sold below cost, so the report has no negative row to shoot",
        )

    def test_one_batch_is_partially_sold_and_one_is_depleted(self):
        from core.models import StockBatch

        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.selling()

        self.assertTrue(StockBatch.objects.filter(quantity_remaining__gt=0).exists())
        self.assertTrue(StockBatch.objects.filter(quantity_remaining=0).exists())

    def test_the_registry_holds_the_eleven_recipes_the_spec_names(self):
        required = {
            "people", "catalogue", "opening", "delivery", "draft", "selling",
            "batches", "out-of-balance", "after-hours", "import", "removal",
        }
        self.assertFalse(
            required - set(seed_demo.REGISTRY),
            f"recipes the spec names but --list does not show: "
            f"{sorted(required - set(seed_demo.REGISTRY))}",
        )
```

The registry assertion is `>=` the eleven names, not equality: chapter tasks add states of their own (`refusals` in Task 9, `history` in Task 25) and those are twelfths, not violations.

- [ ] **Step 2: Run to watch them fail**, then implement `selling()` in `scripts/tutorial/seed_demo.py` and register `"selling"` and `"batches"` in `REGISTRY` (the batch state is a consequence of selling, so `"batches"` may be an alias that re-runs `selling`).

```python
def selling(below_cost: bool = False) -> None:
    """Ring up real orders through checkout(), the only sanctioned order writer.

    Six orders: four today (two on the cashier, two on the owner) and two on the
    cashier yesterday, so chapter 10's date and cashier filters and chapter 11's
    previous-window deltas have something to show. DEMO-0002 is never sold: it is
    chapter 04's row sitting exactly on its threshold.
    """
    import uuid
    from datetime import timedelta

    from django.utils import timezone

    from core.checkout import SaleLine, checkout
    from core.models import Order, Product

    owner = _owner()
    cashier = _cashier()
    shelf = {sku: Product.objects.get(sku=sku) for sku in DEMO_SKUS}

    def sell(actor, picks):
        """picks is [(sku, quantity)]. total_price must be price * quantity or
        checkout raises "The cart price changed" (core/checkout.py:152-156)."""
        lines = [
            SaleLine(shelf[sku].pk, quantity, shelf[sku].price * quantity)
            for sku, quantity in picks
        ]
        return checkout(actor=actor, request_key=uuid.uuid4(), lines=lines)

    # Six lines on one order, which is what makes chapter 09's receipt tall.
    sell(cashier, [(f"DEMO-{index:04d}", 1) for index in range(3, 9)])
    sell(cashier, [("DEMO-0005", 2)])
    sell(owner, [("DEMO-0004", 1), ("DEMO-0010", 1)])
    # Shea Bath Melt opened at threshold * 3 = 36 units, so this empties its only
    # batch: chapter 05's quantity_remaining=0 row becomes a fact, not a claim.
    sell(owner, [("DEMO-0009", shelf["DEMO-0009"].low_stock_threshold * 3)])

    # Yesterday's two, written after the fact because Order.created is
    # auto_now_add (core/models.py:290) and the seeder may not fake a clock.
    yesterday = timezone.localtime() - timedelta(days=1)
    for picks in ([("DEMO-0007", 1)], [("DEMO-0006", 1)]):
        order = sell(cashier, picks)
        Order.objects.filter(pk=order.pk).update(created=yesterday)

    if below_cost:
        _mark_down_and_sell()


def _mark_down_and_sell() -> None:
    """One re-ticketed product, sold under what its shelf batch cost.

    The shop's real shape: the price came down, the batch did not. It is the only
    honest way to get a negative-profit row, because checkout freezes cost_amount
    from the FIFO batches (core/checkout.py:217) and refuses any line whose total
    is not price * quantity.
    """
    import uuid
    from decimal import Decimal

    from core.catalog_imports import PROFIT_RATE_MAX
    from core.checkout import SaleLine, checkout
    from core.models import Product

    product = Product.objects.get(sku="DEMO-0010")  # Sea Salt Body Scrub, cost 55.00
    product.price = Decimal("45.00")
    # The same formula the product dialog uses (core/views.py:505-508); stock is
    # untouched, so Product.save() has nothing to refuse.
    product.profit_rate = min(product.cost / product.price, PROFIT_RATE_MAX)
    product.save(update_fields=["price", "profit_rate"])

    checkout(
        actor=_cashier(),
        request_key=uuid.uuid4(),
        lines=[SaleLine(product.pk, 1, product.price)],
    )
```

Add `_cashier()` beside `_owner()` from Task 5 — identical body, `username=CASHIER_USERNAME`. Register `"selling"` and `"batches"` in `REGISTRY`; the batch state is a consequence of selling, so `"batches"` is an alias that re-runs it. The per-line ceiling is `Decimal("9999.99")` (`core/checkout.py:157`), which the 36-unit Shea line (1 620.00) and the 6-line order (each under 480.00) both sit well inside.

- [ ] **Step 3: Run them to green**, then confirm the six assertions above hold together — the tall order, the emptied batch, the four today and two yesterday, and the below-cost row only when `below_cost=True`.
- [ ] **Step 4: Prove the cashier jar end to end** — `roles.cashier` already exists in `shots.json` and Task 9 used it, so re-shoot `01-04-role-refusal-lands-on-login` after `selling()` has run and confirm it is still the login page for `demo.rep`. A cashier with orders of their own must still be refused `/products/`; if the frame changes, the refusal is not the cashier's but the seed order's, and that difference belongs in chapter 01's prose. Task 23's `08-01-till-versus-hub` is the frame that shows a cashier landing on the till.
- [ ] **Step 5: Run to green, commit** — `"Ring up real sales for the till and report chapters"`.

### Task 22: The 80 mm sheet preview pipeline

**Files:**
- Modify: `scripts/tutorial/shoot.py` (add `render_receipt_preview()`)
- Test: `scripts/tutorial/tests/test_receipt_preview.py`, created with the same header as `test_seed_recipes.py` — `import tempfile`, `from pathlib import Path`, `from django.contrib.auth import get_user_model`, `from django.test import TestCase, override_settings`, `from scripts.tutorial import seed_demo, shoot`, and `from core.models import Order` — because these tests touch the database, and with **the same `setUpModule`/`tearDownModule` media redirect**: `catalogue()` is called here too.

**Interfaces:**
- Consumes: `seed_demo.selling()` (Task 21), `core.views.receipt_sheet_length_mm`, `settings.RECEIPT_COLOPHON_HEIGHT_MM`, `settings.COMPANY_INFO`, `static/css/receipt.css`, `core/templates/core/orders/prints/order_details.html`.
- Produces: `shoot.render_receipt_preview(order) -> str` (a standalone HTML document) and, as a by-product of Step 3, the real downloaded artifacts in `docs/onboarding/samples/`.

- [ ] **Step 1: Failing test**

```python
class SheetPreviewTests(TestCase):
    def test_the_preview_is_80mm_wide_and_carries_the_receipt_stylesheet(self):
        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.selling()
        order = Order.objects.order_by("-created").first()

        html = shoot.render_receipt_preview(order)  # a standalone HTML string

        self.assertIn("width: 80mm", html)
        self.assertIn("receipt.css", html)
        self.assertIn(order.code, html)

    def test_the_receipt_pdf_keeps_the_name_the_app_gives_it(self):
        """The manual tells a reader what to look for in Downloads, so the harness
        may not quietly rename the file to something tidier."""
        seed_demo.catalogue()
        seed_demo.opening()
        seed_demo.selling()
        order = Order.objects.order_by("-created").first()
        Account = get_user_model()
        self.client.force_login(Account.objects.get(username=seed_demo.OWNER_USERNAME))

        response = self.client.get(f"/orders/view-order/{order.id}/1/print-pdf")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response["Content-Disposition"],
            r'filename="Invoice-[0-9A-Z]{1,6}-\d{14}\.pdf"',
        )
```

`{order.id}/1` — the trailing number is decorative. `core/urls.py:162` declares it `<int:order_number>` and `print_order_pdf` only puts it in the context (`core/views.py:1357`); the real order is fetched by `get_receipt(request, order_id)`. The regex keeps the quotes because `utils.py:148-150` writes `attachment; filename="..."`, and `[0-9A-Z]` because `generate_code` draws from uppercase letters and digits only (`utils.py:180`).

`render_receipt_preview()` has to set the page width itself: `static/css/receipt.css` deliberately does **not** declare one — its header comment says WeasyPrint only takes fixed heights, so `print_order_pdf` passes `page_size_mm=(80, receipt_sheet_length_mm(order, settings.COMPANY_INFO, RECEIPT_COLOPHON_HEIGHT_MM))` at `core/views.py:1369-1376` (`RECEIPT_COLOPHON_HEIGHT_MM = 27.0` is `core/views.py:1322`). A browser renderer needs `width: 80mm` on the wrapper instead.

- [ ] **Step 2: Implement `render_receipt_preview()` in `shoot.py`** — render `core/templates/core/orders/prints/order_details.html` (the PDF's template, confirmed at `core/views.py:1365`; the *screen* receipt at `core/views.py:1318` renders `core/orders/order_details.html`, a different file, and the preview must follow the paper), with the same context the view builds (`order`, `order_number`, `logo_data_uri`, `developer` — `core/views.py:1355-1360`) and the same `COMPANY_INFO`, inline `static/css/receipt.css` inside a `<style>` block that opens with `/* inlined from css/receipt.css */` (the marker the first test asserts on), write `docs/onboarding/samples/receipt-preview.html`, and screenshot it at 302 px wide (80 mm ≈ 302 px at 96 dpi). The caption in chapter 09 must state that the PDF is authoritative and the PNG is the same markup.
- [ ] **Step 3: Download the real artifacts** into `docs/onboarding/samples/` through the scratch server with the owner jar: the receipt PDF from `/orders/view-order/{order_id}/{order_number}/print-pdf`, the day-batch PDF from `/orders/checks-orders/{day}/{users}/print` (the misspelled segment is the real route), the report PDF from `/orders/sales-reports/print-pdf/`, and both CSVs from `/orders/check-orders/export-csv/` and `/orders/sales-reports/export-csv/`. Save each under the filename its own `Content-Disposition` carries — read it from the header rather than inventing one, because chapters 09 and 10 tell the reader what to look for in Downloads. The five names the app produces are `Invoice-<code>-<ddMMyyyyHHmmss>.pdf` (`core/views.py:1363`), `Sale_<ddMMyyyy>.pdf` (`:1301`), `Reports_<stamp>.pdf` (`:1569`), `orders_<yyyyMMdd_HHmmss>.csv` (`:978`) and `sales_report_<windowStart>_<stamp>.csv` (`:1501`); if what lands differs from those, the app changed and the chapter text must change with it.
- [ ] **Step 4: Run to green, commit** — `"Render the 80 mm sheet as paper and download the real artifacts"`.

### Task 23: Chapter 08 — Work the till

- [ ] **Step 1: Re-verify** — the POS grid page size (12), the cart ceiling with no message, `Void Cart` semantics, the stale-cart error band ("The cart price changed. Refresh the register." — `core/checkout.py:150-156`, re-read), the missing idempotency key in `pos_register.html`, the takings chip out-of-band swap, and the mobile bottom bar.
- [ ] **Step 2: Manifest** — `08-01-till-versus-hub`, `08-02-grid-with-badges`, `08-03-search-and-scroll`, `08-04-cart-ceiling`, `08-05-settlement-panel`, `08-06-void-cart-button`, `08-07-stale-cart-error`, `08-08-mobile-bottom-bar`, `08-09-after-hours-no-receipt-button` (9 shots; 6 of them are this phase's counted entries).
- [ ] **Step 3: Shoot and look** — `08-09` must come from the `after-hours` recipe and show the settlement panel with **no** receipt control. `08-04` must show the stepper stopped with no message — that absence is the point of the frame.
- [ ] **Step 4: Prose** — "Notes & limits" says plainly that a double tap books twice because the register sends no idempotency key, that tender type and change due do not exist, that refunds and voids of a booked order do not exist, and that barcode lookup is not integrated.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the till chapter including the double-tap fact"`.

### Task 24: Chapter 09 — Print a customer receipt

- [ ] **Step 1: Re-verify** — the anatomy of `order_details.html`, `COMPANY_EMAIL` blanking in `.env` and its effect on roll length, `TOTAL (GHS)`, the colophon, and the three entry points (settlement panel, inspector, report ledger icon).
- [ ] **Step 2: Manifest** — `09-01-sheet-preview`, `09-02-pdf-page`, `09-03-anatomy-annotated`, `09-04-email-blanked`, `09-05-three-entry-points`, `09-06-cashier-one-shot-loop` (6 shots).
- [ ] **Step 3: Shoot and look** — `09-02` is the downloaded PDF rendered to an image; if headless Chromium cannot rasterise it, capture the browser's own viewer and say so in the caption rather than substituting the preview PNG.
- [ ] **Step 4: Prose** — "print" means download; booked orders are immutable; the receipt says "Served by" because it records a cashier, not a refund.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the receipt chapter from paper and PDF side by side"`.

---

# Phase 5 — Looking back

Exit: a negative-profit row visible in the report ledger, the day-batch PDF named exactly as the app names it; 10 entries.

### Task 25: The multi-day, multi-cashier and below-cost state

- [ ] **Step 1: Failing test** — assert a report window contains at least one order whose line profit is negative and at least one cashier whose share is non-zero, using `seed_demo.selling(below_cost=True)` from Task 21.
- [ ] **Step 2: Implement the report-window helper** `seed_demo.history()` that spreads orders across seven days for both cashiers, then run to green.
- [ ] **Step 3: Commit** — `"Spread sales across a week for the report chapter"`.

### Task 26: Chapter 10 — The orders and receipts ledger

- [ ] **Step 1: Re-verify** — the four KPI tiles and their empty states, the `/` receipt-code search, cashier and date filters, `Print Batch` disabled until a date is chosen, the whole-row click into the inspector, the 6-column CSV, the `?view=orders&q=` deep link that clears the date, and the ledger page size (10).
- [ ] **Step 2: Manifest** — `10-01-ledger-default`, `10-02-kpi-empty`, `10-03-code-search`, `10-04-filters`, `10-05-print-batch-disabled`, `10-06-print-batch-enabled`, `10-07-inspector`, `10-08-csv-opened` (8 shots).
- [ ] **Step 3: Shoot and look**, confirming `10-06`'s PDF lands in `samples/` with the app's own filename.
- [ ] **Step 4: Prose** — quote the deep-link quirk as a behaviour, not a bug; the CSV's six columns are listed in the order the file writes them.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the orders ledger chapter including its deep-link quirk"`.

### Task 27: Chapter 11 — Sales reports and exports

- [ ] **Step 1: Re-verify** — the four presets, the live range pill, custom-by-typing and the silent fallback to Today, the reversed-date swap, previous-window deltas, the by-cashier share bar, the by-department panel, the transaction ledger's `+` green and rose negative-profit rows, the 12-column CSV that splits actual from estimated cost, and the A4 report PDF.
- [ ] **Step 2: Manifest** — `11-01-report-default`, `11-02-presets`, `11-03-custom-range-fallback`, `11-04-reversed-dates`, `11-05-kpi-deltas`, `11-06-cashier-share`, `11-07-department-panel`, `11-08-ledger-negative-row`, `11-09-report-pdf` (9 shots).
- [ ] **Step 3: Shoot and look** — `11-08` is the phase's exit proof: the rose row must be real, from `below_cost=True`.
- [ ] **Step 4: Prose** — explain the estimated-cost split in shop words; it is the one place the screen and the CSV disagree, and the reader must know which to trust.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the reports chapter with a real loss on the ledger"`.

---

# Phase 6 — People and upkeep

Exit: all 54 routes mapped **and** captured, the full matrix, `SHOTLOG.md` and the index generated, one commit closing the manual.

### Task 28: The deactivated-account state

- [ ] **Step 1: Failing test** — assert `demo.locked` cannot sign in and that the bounce is the login page, using Django's test client in the same module (this is the one harness test that legitimately exercises login).
- [ ] **Step 2: Implement `seed_demo.locked_out()` returning the deactivated account; run to green; commit** — `"Keep a locked account for the roles chapter"`.

### Task 29: Chapter 12 — Accounts and roles

- [ ] **Step 1: Re-verify** — `authapp/views.py` `account_update_details` and its 403 on the owner's own row, `NewAccountForm.Meta.fields` carrying the names (this lane's `8d716dd`), `AccountSetPasswordForm`'s mismatch text, `telephone` `max_length=10`, and the three self-service 403s.
- [ ] **Step 2: Manifest** — `12-01-roster`, `12-02-create-dialog-names-land`, `12-03-edit-details-dialog`, `12-04-phone-too-long`, `12-05-reset-mismatch`, `12-06-deactivate-confirm`, `12-07-locked-account-bounced` (7 shots).
- [ ] **Step 3: Shoot and look** — `12-02` must show the new row's Name column carrying the typed names, not the handle; `12-04` must show the inline error with the dialog still open.
- [ ] **Step 4: Prose** — the table of what a cashier can never reach, and the fact that no email is ever sent, so a forgotten password is a walk.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the accounts chapter on the fixed name behaviour"`.

### Task 30: Chapter 13 — Known gaps and upkeep

- [ ] **Step 1: Re-verify** — `/orders/check-orders/` and `/days` reachable only by typing the URL, the `retrieve_todays_sale` year-blending bug, `/admin/` as read-only history, `check_inventory` and `load_csv` management commands (`ls core/management/commands/`), the 0%-forever import when the worker is down, log locations, and the nightly dump.
- [ ] **Step 2: Manifest** — `13-01-legacy-screen`, `13-02-admin-site`, `13-03-import-progress-zero`, `13-04-check-inventory-output` (4 shots).
- [ ] **Step 3: Shoot and look** — `13-03` requires stopping the *tutorial* worker only, never the shop's.
- [ ] **Step 4: Prose** — the promises-versus-reality table: one row per overpromising label, each citing the chapter where the reader meets it. This is the only place a gap may be collected, and every gap must also have been named at the moment of contact in its own chapter.
- [ ] **Step 5: Gates green, suite green, commit** — `"Write the gaps chapter so the manual stops short of lying"`.

### Task 31: Close the manual

- [ ] **Step 1: Generate the index** — rewrite `docs/onboarding/README.md`: the thirteen chapters in reading order with one-line "what this is for" taken from each chapter's own first block, a "read this first if you are the cashier" pointer to 01/08/09, the route-to-chapter table copied from the spec, and the re-shoot playbook (`run_demo_server.ps1` → `seed_demo.py --reset` → `shoot.py --chapter` → `verify.py`).
- [ ] **Step 2: Run every gate**

Run: `DJANGO_SETTINGS_MODULE=scripts.tutorial.demo_settings .venv/Scripts/python.exe -m scripts.tutorial.verify`
Expected: `verify: all gates green` — 54 routes mapped, every chapter image present, no orphan PNG, no prose path that does not resolve, every manifest shot logged.

Run: `.venv/Scripts/python.exe manage.py test --keepdb > /tmp/p6.log 2>&1; echo "exit=$?"`
Expected: `exit=0`

- [ ] **Step 3: Read the whole manual as a new person**, on the phone viewport for chapters 01 and 08. Anything a caption claims that no frame shows is a defect in the chapter, not in the frame.
- [ ] **Step 4: Commit**

```bash
git add docs/onboarding/README.md docs/onboarding/SHOTLOG.md docs/onboarding/samples
git commit -m "Close the onboarding manual with its index and shot log"
```

---

## Self-review notes

- **Spec coverage:** capture engine (Tasks 1–2, 6, 12, 22), the fourteen recipes the registry ends up holding — the eleven the spec names plus `refusals`, `history` and `locked_out` (Tasks 4–5, 9, 12, 14, 16–17, 21, 25, 28), thirteen chapters (Tasks 10–11, 13, 15, 18–20, 23–24, 26–27, 29–30), four gates (Task 7), template, index and playbook (Tasks 3, 8, 31), honest-documentation ground rules (Step 4 of every chapter task). The spec's "Chapter anatomy" and "Ground rules" are requirements enforced by `_template.md` (Task 3) and by each chapter's Step 1 re-verification.
- **Two deviations from the spec, both deliberate and recorded in the spec itself:** isolation moved from an exported `POSTGRES_DB` to a settings shim, because `load_dotenv(..., override=True)` made the exported value lose; and the demo worker got its own Redis index and queue, which the spec did not require but the shop's live worker made unsafe.
- **Contracts re-read against the working tree, not remembered.** The seed/verify code in Tasks 2, 4–7, 14, 16–17, 21–22 was checked field by field against `core/models.py`, `core/checkout.py:20-73`, `core/inventory.py`, `core/batch_views.py:956-1012` and `core/views.py:1318-1375`. That pass deleted invented names (`core.StockReceiptLine`, `StockReceipt.lines`, `StockReceiptDraft.lines_json`, `models.low_threshold_expr()`, `StockBatch.remaining`), fixed the receipt draft payload key list to the real `{"product_id","unit_cost","selling_price","units"}` with all-string values, replaced `create_test_db(keepdb=True)` (which would have made a database called `test_myshop_tutorial`) with `scratchdb.py`, moved the Celery worker ahead of the foreground `runserver` so it is reachable and stops on its own `-Q tutorial` queue, and made `_guard()` refuse a bare run instead of quietly adopting the shim through `setdefault`.
- **Route count is 54 in the working tree, 59 matrix entries.** `HEAD` has 53; `/help/` and four `receipts/` routes are the other lane's uncommitted work. `verify.py` reads the number from the spec rather than hard-coding it, and reports unmapped routes in both directions, so a route added later fails the gate instead of being edited away.
- **A second pass over the steps that only had prose.** Task 21 now carries the real `selling()` and `_mark_down_and_sell()` bodies, because the negative-profit row cannot be written from a description: `checkout` refuses any line whose `total_price` is not `price * quantity` (`core/checkout.py:152-156`), so below-cost is a markdown plus a sale, not a smaller number in the line. Task 22's filename test now arranges its own response, and its regex keeps the quotes `utils.py:148-150` actually writes. `{day}` resolves to the scratch install's own today rather than a frozen date, so chapter 10's batch print is never a page of nothing, and `{user}` was renamed `{users}` to match the token the prose and the lookup table both have to use.
- **Remaining runtime unknowns are small and each is caught by a step that looks at the frame.** The drawer is verified plain JavaScript (`templates/partials/header.html:149,162` toggled by `templates/_base.html:135-144`), and the dialog selectors are verified (`templates/partials/modal.html:10` sets `role="dialog"` inside `#modal_root`; "Receive Delivery" is `core/templates/core/products/products.html:56`). What cannot be known before running is how the pages behave under htmx timing on a cold scratch DB — table polls, `hx-trigger="load"` swaps and the POS cart's own reloads. That is why every chapter task has a "shoot and look" step and why no chapter may claim something its PNGs do not show.
- **The other lane's uncommitted templates are a live risk to Phases 3–4.** `core/templates/core/orders/prints/order_details.html`, `receive_stock.html` and `pos_register.html` are being edited while this plan photographs them. Each chapter task's Step 1 re-reads its own files immediately before capturing, so a moved label or renamed route surfaces as a caption correction rather than a stale screenshot; if Phase 3 or 4 finds a template it cannot make consistent, the honest move is to re-shoot, not to describe what used to be there.
