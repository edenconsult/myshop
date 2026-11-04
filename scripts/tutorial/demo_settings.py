"""Settings for the disposable tutorial install. Never used by the shop.

Star-importing the project settings runs its load_dotenv(..., override=True), so
every override below is applied after .env has had its say and therefore wins.
"""

from myshopproject.settings import *  # noqa: F403

from scripts.tutorial.isolation import (
    BROKER_DB_INDEX,
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
