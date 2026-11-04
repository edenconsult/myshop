"""Settings for the disposable tutorial install. Never used by the shop.

Star-importing the project settings runs its load_dotenv(..., override=True), so
every override below is applied after .env has had its say and therefore wins.
"""

import os
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

# Celery's namespace config source takes these two keys from the environment, and
# load_dotenv(override=True) has just written the shop's URL into it, so the
# attributes above never reach an app or a worker on their own. The shim is the
# last writer, so it writes there too — otherwise a demo task is published into the
# shop's broker and run by the shop's worker against the shop's own database.
os.environ["CELERY_BROKER_URL"] = _broker
os.environ["CELERY_RESULT_BACKEND"] = _broker

# One folder below the shop's own photos, not beside them: media/ is git-ignored as
# a whole, so the scratch tree stays untracked without touching .gitignore.
MEDIA_ROOT = str(Path(MEDIA_ROOT) / DEMO_MEDIA_FOLDER)  # noqa: F405
