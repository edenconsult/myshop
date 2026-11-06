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
        has to be proven against the real settings object, not only the fakes. The
        base URL is passed so all five coordinates are pinned, not four."""
        from scripts.tutorial import isolation

        isolation.assert_isolated(self.demo_settings, base_url=isolation.DEMO_BASE_URL)

    def test_puts_the_broker_where_the_celery_app_actually_looks(self):
        """`config_from_object(..., namespace="CELERY")` reads the two broker keys
        from the environment, and the star-import's load_dotenv(override=True) has
        already put the shop's URL there — so overriding the module attribute alone
        leaves a demo task in the shop's broker. Measured on this checkout: the
        queue came through (absent from .env) and the broker did not."""
        import os

        from scripts.tutorial import isolation

        for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
            self.assertTrue(
                os.environ[key].endswith(f"/{isolation.BROKER_DB_INDEX}"),
                f"{key} in the environment is {os.environ.get(key)!r}",
            )


def tearDownModule():
    """The shim rewrites the two broker keys in the environment — that is the fix it
    exists to prove — and this process runs the rest of the suite afterwards, so the
    shop's own values go back. Reading them from the live settings module rather than
    hard-coding them keeps this honest if .env changes."""
    import os

    from myshopproject import settings as live

    for key in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        os.environ[key] = str(getattr(live, key))
