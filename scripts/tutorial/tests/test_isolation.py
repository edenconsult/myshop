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

    def test_a_live_database_is_refused_even_with_a_scratch_url(self):
        """The two checks are independent: a scratch port does not excuse the shop's books."""
        with self.assertRaisesRegex(isolation.NotScratchInstall, "database"):
            isolation.assert_isolated(
                scratch(DATABASES={"default": {"NAME": "myshopproject"}}),
                base_url=isolation.DEMO_BASE_URL,
            )
