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
