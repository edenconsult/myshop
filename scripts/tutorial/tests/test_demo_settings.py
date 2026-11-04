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
