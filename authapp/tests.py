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


class AccountsPageAccessTests(TestCase):
    """Only the owner reaches the accounts page; a salesperson is bounced."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )
        cls.rep = Account.objects.create_user(
            username="kb", password="unused", user_type="SALEPERSON"
        )

    def test_the_url_exists(self):
        self.assertEqual(reverse("auth:accounts"), "/accounts/")

    def test_salesperson_is_bounced_from_the_list(self):
        self.client.force_login(self.rep)

        response = self.client.get(reverse("auth:accounts"))

        self.assertEqual(response.status_code, 302)

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse("auth:accounts"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse(settings.LOGIN_URL)}?next={reverse('auth:accounts')}",
            fetch_redirect_response=False,
        )

    def test_the_owner_sees_every_account(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("auth:accounts"))

        self.assertEqual(response.status_code, 200)
        usernames = {account.username for account in response.context["accounts"]}
        self.assertEqual(usernames, {"boss", "kb"})


class AccountOperationsTests(TestCase):
    """Create a salesperson, reset a password, deactivate/reactivate — the
    owner's whole roster, and nothing that touches their own account."""

    strong_password = "Str0ng-pass-999"

    @classmethod
    def setUpTestData(cls):
        cls.owner = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )
        cls.rep = Account.objects.create_user(
            username="kb", password=cls.strong_password, user_type="SALEPERSON"
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_makes_a_salesperson_who_can_sign_in(self):
        response = self.client.post(
            reverse("auth:account-create"),
            {
                "username": "ama",
                "first_name": "Ama",
                "last_name": "Mensah",
                "password1": self.strong_password,
                "password2": self.strong_password,
            },
        )

        self.assertEqual(response.status_code, 302)
        created = Account.objects.get(username="ama")
        self.assertEqual(created.user_type, "SALEPERSON")
        self.assertTrue(
            self.client.login(username="ama", password=self.strong_password)
        )

    def test_create_never_opens_an_admin_seat(self):
        """The form has no role field; a forged one must not be honoured."""
        self.client.post(
            reverse("auth:account-create"),
            {
                "username": "sneak",
                "first_name": "Sne",
                "last_name": "Ak",
                "password1": self.strong_password,
                "password2": self.strong_password,
                "user_type": "ADMIN",
            },
        )

        self.assertEqual(Account.objects.get(username="sneak").user_type, "SALEPERSON")

    def test_create_rejects_a_taken_username(self):
        response = self.client.post(
            reverse("auth:account-create"),
            {
                "username": "kb",
                "first_name": "Other",
                "last_name": "Person",
                "password1": self.strong_password,
                "password2": self.strong_password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["create_form"].errors)
        self.assertEqual(Account.objects.filter(username="kb").count(), 1)

    def test_create_rejects_a_weak_password(self):
        response = self.client.post(
            reverse("auth:account-create"),
            {
                "username": "weak",
                "first_name": "Weak",
                "last_name": "Pass",
                "password1": "password",
                "password2": "password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Account.objects.filter(username="weak").exists())

    def test_reset_replaces_the_password(self):
        response = self.client.post(
            reverse("auth:account-reset-password", args=[self.rep.pk]),
            {"new_password1": self.strong_password, "new_password2": self.strong_password},
        )

        self.assertEqual(response.status_code, 302)
        self.rep.refresh_from_db()
        self.assertTrue(
            self.rep.check_password(self.strong_password)
        )

    def test_reset_mismatched_confirmation_is_rejected(self):
        response = self.client.post(
            reverse("auth:account-reset-password", args=[self.rep.pk]),
            {"new_password1": self.strong_password, "new_password2": "Other-pass-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["reset_form"].errors)

    def test_the_owner_cannot_reset_their_own_password_here(self):
        response = self.client.post(
            reverse("auth:account-reset-password", args=[self.owner.pk]),
            {"new_password1": self.strong_password, "new_password2": self.strong_password},
        )

        self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("unused"))

    def test_deactivate_blocks_the_next_login(self):
        response = self.client.post(
            reverse("auth:account-toggle-active", args=[self.rep.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.rep.refresh_from_db()
        self.assertFalse(self.rep.is_active)
        self.client.logout()
        self.assertFalse(
            self.client.login(username="kb", password="unused")
        )

    def test_reactivate_restores_access(self):
        Account.objects.filter(pk=self.rep.pk).update(is_active=False)

        self.client.post(reverse("auth:account-toggle-active", args=[self.rep.pk]))

        self.rep.refresh_from_db()
        self.assertTrue(self.rep.is_active)

    def test_the_owner_cannot_lock_themselves_out(self):
        response = self.client.post(
            reverse("auth:account-toggle-active", args=[self.owner.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)


class AccountsMenuEntryTests(TestCase):
    """The drawer carries 'Manage accounts' for the owner only."""

    def render_header(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("partials/header.html", {"request": request})

    def test_owner_sees_the_link(self):
        owner = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )

        html = self.render_header(owner)

        self.assertIn(reverse("auth:accounts"), html)

    def test_salesperson_does_not_see_the_link(self):
        rep = Account.objects.create_user(
            username="kb", password="unused", user_type="SALEPERSON"
        )

        html = self.render_header(rep)

        self.assertNotIn(reverse("auth:accounts"), html)


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


class HeaderRoleNavTests(TestCase):
    """A cashier's nav is the register and nothing else — the desktop bar and
    the mobile drawer are one surface, so both have to agree."""

    def render_header(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("partials/header.html", {"request": request})

    @classmethod
    def setUpTestData(cls):
        cls.owner = Account.objects.create_user(
            username="boss", password="unused", user_type="ADMIN"
        )
        cls.rep = Account.objects.create_user(
            username="kb", password="unused", user_type="SALEPERSON"
        )

    def test_the_owner_is_offered_every_section(self):
        html = self.render_header(self.owner)

        for label in (
            "Central Hub",
            "Products &amp; Stock",
            "Sales Reports",
            "Point of Sale",
        ):
            with self.subTest(label=label):
                self.assertIn(label, html)

    def test_the_cashier_is_offered_the_register_only(self):
        html = self.render_header(self.rep)

        self.assertIn("Point of Sale", html)
        for label in ("Central Hub", "Products &amp; Stock", "Orders", "Sales Reports"):
            with self.subTest(label=label):
                self.assertNotIn(f"<span>{label}</span>", html)

    def test_the_cashier_is_linked_to_no_owner_route(self):
        html = self.render_header(self.rep)

        for path in (
            reverse("core:products"),
            reverse("core:orders"),
            reverse("core:today-orders"),
            reverse("core:sales-report"),
        ):
            with self.subTest(path=path):
                self.assertNotIn(path, html)

    def test_both_roles_get_a_register_link_the_shortcut_can_find(self):
        for user in (self.owner, self.rep):
            with self.subTest(user_type=user.user_type):
                self.assertIn("data-pos-link", self.render_header(user))

    def test_the_cashier_register_link_lands_at_the_hub_root(self):
        """A cashier has no /sales/ page any more, so the nav item has to point
        at the shared register."""
        html = self.render_header(self.rep)

        self.assertIn(f'href="{reverse("core:base")}"', html)
