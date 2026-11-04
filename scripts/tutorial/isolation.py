"""The only module that says what 'safe to write demo data' means.

Every entry point calls assert_isolated() before touching anything, and it reads
resolved settings rather than os.environ: myshopproject/settings.py loads .env
with override=True, so an exported POSTGRES_DB loses to the file and a launcher
that trusted the environment would have run its migrations against the shop's
own books.
"""

from urllib.parse import urlsplit

SCRATCH_DB = "myshop_tutorial"
SHIM_MODULE = "scripts.tutorial.demo_settings"
DEMO_HOST = "127.0.0.1"
SCRATCH_PORT = 8010
DEMO_BASE_URL = f"http://{DEMO_HOST}:{SCRATCH_PORT}"
BROKER_DB_INDEX = 15
TUTORIAL_QUEUE = "tutorial"


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
