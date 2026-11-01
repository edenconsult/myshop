from django.conf import settings
from django.contrib.auth import authenticate
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from urllib.parse import urlsplit

from authapp.models import Account


class ProfileViewTests(TestCase):
    """The account page a user reaches from the header menu."""

    def setUp(self):
        self.user = Account.objects.create_user(
            username="kb",
            password="Current-pass-123",
            first_name="Kofi",
            last_name="Braff",
        )
        self.user.email = "kofi@example.com"
        self.user.telephone = "0244000000"
        self.user.save()
        self.url = reverse("auth:profile")

    def test_anonymous_visitor_is_sent_to_login(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse(settings.LOGIN_URL)}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_form_starts_with_the_signed_in_user_details(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        form = response.context["form"]
        self.assertEqual(form["first_name"].value(), "Kofi")
        self.assertEqual(form["last_name"].value(), "Braff")
        self.assertEqual(form["email"].value(), "kofi@example.com")
        self.assertEqual(form["telephone"].value(), "0244000000")

    def test_saving_edits_updates_the_account(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "first_name": "Ama",
                "last_name": "Mensah",
                "email": "ama@example.com",
                "telephone": "0201112222",
            },
        )

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, self.url)
        self.assertEqual(self.user.first_name, "Ama")
        self.assertEqual(self.user.last_name, "Mensah")
        self.assertEqual(self.user.email, "ama@example.com")
        self.assertEqual(self.user.telephone, "0201112222")

    def test_invalid_email_is_rejected_without_saving(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "first_name": "Ama",
                "last_name": "Mensah",
                "email": "not-an-email",
                "telephone": "0201112222",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["email"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Kofi")
        self.assertEqual(self.user.email, "kofi@example.com")


class PasswordChangeViewTests(TestCase):
    """Reuses Django's own view so the old password is verified and the
    session is re-hashed instead of dropping the user out of the app."""

    current_password = "Current-pass-123"
    new_password = "Brand-new-pass-456"

    def setUp(self):
        self.user = Account.objects.create_user(
            username="kb", password=self.current_password
        )
        self.url = reverse("auth:password_change")
        self.done_url = reverse("auth:password_change_done")

    def change(self, client, old_password, new_password):
        return client.post(
            self.url,
            {
                "old_password": old_password,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse(settings.LOGIN_URL)}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_wrong_current_password_keeps_the_account_unlocked(self):
        self.client.force_login(self.user)

        response = self.change(self.client, "Not-my-password", self.new_password)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["old_password"])
        self.assertIsNotNone(authenticate(username="kb", password=self.current_password))

    def test_new_password_works_and_the_old_one_stops_working(self):
        self.client.force_login(self.user)

        response = self.change(self.client, self.current_password, self.new_password)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, self.done_url)
        self.assertIsNotNone(authenticate(username="kb", password=self.new_password))
        self.assertIsNone(authenticate(username="kb", password=self.current_password))

    def test_user_stays_signed_in_after_changing(self):
        self.client.force_login(self.user)

        self.change(self.client, self.current_password, self.new_password)
        response = self.client.get(self.done_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.user.username, "kb")


class HeaderUserMenuTests(TestCase):
    """The header chip is the only way into the account pages, and it stays out
    of the Django admin entirely — admins go there directly, reps never."""

    def render_header(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("partials/header.html", {"request": request})

    def test_chip_links_to_the_profile_and_password_pages(self):
        user = Account.objects.create_user(username="kb", password="unused")

        html = self.render_header(user)

        self.assertIn(reverse("auth:profile"), html)
        self.assertIn(reverse("auth:password_change"), html)

    def test_no_role_is_offered_the_django_admin_link(self):
        admin = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )
        rep = Account.objects.create_user(
            username="kb", password="unused", user_type="SALEPERSON"
        )

        for user in (admin, rep):
            with self.subTest(user_type=user.user_type):
                self.assertNotIn("/admin/", self.render_header(user))

    def test_the_chip_never_shows_a_fixed_store_label(self):
        user = Account.objects.create_user(username="kb", password="unused")

        html = self.render_header(user)

        self.assertNotIn("Store #", html)

    def test_drawer_shows_the_account_role_rather_than_a_fixed_one(self):
        rep = Account.objects.create_user(
            username="kb", password="unused", user_type="SALEPERSON"
        )
        admin = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )

        rep_html = self.render_header(rep)
        admin_html = self.render_header(admin)

        self.assertIn("SALEPERSON", rep_html)
        self.assertNotIn("Administrator", rep_html)
        self.assertIn("ADMIN", admin_html)
