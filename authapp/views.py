from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from authapp.forms import (
    AccountSetPasswordForm,
    NewAccountForm,
    ProfileForm,
    profile_form_for,
)
from utils import can_ring_up, is_admin


def _accounts_context(request, bound_form=None):
    model = get_user_model()
    context = {
        "accounts": model.objects.order_by("-date_joined"),
        "create_form": NewAccountForm(),
        "reset_form": AccountSetPasswordForm(),
        "flash_created": request.GET.get("created"),
        "flash_reset": request.GET.get("reset"),
        "flash_updated": request.GET.get("updated"),
    }
    # one form per editable row, so Django's own field errors sit inline in that
    # row's dialog instead of being copied around by script. The owner's own row
    # is left out: their details belong to auth:profile.
    edit_forms = []
    for account in context["accounts"]:
        if account.pk == request.user.pk:
            continue
        if bound_form is not None and bound_form.instance.pk == account.pk:
            edit_forms.append((account.pk, bound_form))
        else:
            edit_forms.append((account.pk, profile_form_for(account)))
    context["edit_forms"] = edit_forms
    if bound_form is not None:
        # the rejected save re-renders the roster, so the row whose dialog was
        # open must reopen carrying what was typed
        context["edit_open"] = bound_form.instance.username
        context["edit_open_pk"] = bound_form.instance.pk
    # after a rejected reset the dialog reopens on the same row, so its POST
    # target must survive the re-render
    reset_open = request.GET.get("reset_open")
    if reset_open:
        target_pk = (
            model.objects.filter(username=reset_open).values_list("pk", flat=True).first()
        )
        if target_pk is not None:
            context["reset_open"] = reset_open
            context["reset_action_pk"] = target_pk
    return context


@login_required
@user_passes_test(is_admin)
def accounts(request):
    """Owner-only roster: everyone who can sign in, newest first."""
    return render(request, "authapp/accounts.html", _accounts_context(request))


@require_POST
@login_required
@user_passes_test(is_admin)
def account_create(request):
    form = NewAccountForm(request.POST)
    if not form.is_valid():
        context = _accounts_context(request)
        context["create_form"] = form
        return render(request, "authapp/accounts.html", context)
    account = form.save()
    return redirect(f"{reverse('auth:accounts')}?{urlencode({'created': account.username})}")


@require_POST
@login_required
@user_passes_test(is_admin)
def account_update_details(request, account_id):
    account = get_object_or_404(get_user_model(), id=account_id)
    # the owner's own details stay under auth:profile, where they are edited by
    # the person they belong to
    if account.pk == request.user.pk:
        return HttpResponseForbidden("Use Your profile for your own account.")

    form = profile_form_for(account, request.POST)
    if not form.is_valid():
        return render(
            request,
            "authapp/accounts.html",
            _accounts_context(request, bound_form=form),
        )
    form.save()
    return redirect(f"{reverse('auth:accounts')}?{urlencode({'updated': account.username})}")


@require_POST
@login_required
@user_passes_test(is_admin)
def account_reset_password(request, account_id):
    account = get_object_or_404(get_user_model(), id=account_id)
    # the owner's own password stays under auth:password_change, where the old
    # password is verified and the session is re-hashed
    if account.pk == request.user.pk:
        return HttpResponseForbidden("Use Change password for your own account.")

    form = AccountSetPasswordForm(request.POST)
    if not form.is_valid():
        # request.GET still carries ?reset_open=<username>, which reopens the
        # dialog on the same row via _accounts_context
        context = _accounts_context(request)
        context["reset_form"] = form
        return render(request, "authapp/accounts.html", context)
    account.set_password(form.cleaned_data["new_password1"])
    account.save()
    return redirect(f"{reverse('auth:accounts')}?{urlencode({'reset': account.username})}")


@require_POST
@login_required
@user_passes_test(is_admin)
def account_toggle_active(request, account_id):
    account = get_object_or_404(get_user_model(), id=account_id)
    if account.pk == request.user.pk:
        return HttpResponseForbidden("You cannot deactivate your own account.")
    account.is_active = not account.is_active
    account.save(update_fields=["is_active"])
    return redirect(reverse("auth:accounts"))


def signin(request):
    """Signin"""
    if request.user.is_authenticated and can_ring_up(request.user):
        return redirect('core:base')

    validations: dict[str, str | bool] = {}
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        if not username:
            validations["username_error"] = True
            validations["username_error_message"] = "Username is empty"
        if not password:
            validations["password_error"] = True
            validations["password_error_message"] = "Password is empty"

        if validations.get("username_error") or \
                validations.get("password_error"):
            context = {"validations": validations, "username": username}
            return render(request, "authapp/login.html", context)

        user_exists = get_user_model().objects.filter(username=username).exists()
        if not user_exists:
            validations["form_has_error"] = True
            validations["form_error_message"] = "Username or password is incorrect!"
            context = {"validations": validations, "username": username}
            return render(request, "authapp/login.html", context)
        else:
            authenticated_user = authenticate(
                request, username=username, password=password
            )
            if authenticated_user is None:
                validations["form_has_error"] = True
                validations["form_error_message"] = "Username or password is incorrect!"
                context = {"validations": validations, "username": username}
                return render(request, "authapp/login.html", context)
            else:
                login(request, authenticated_user)
                return redirect("auth:login_success")

    context = {"validations": validations}
    return render(request, "authapp/login.html", context)


@login_required
def login_success(request):
    if can_ring_up(request.user):
        return redirect("core:base")
    return HttpResponse(b"Unauthorized Access.")


@login_required
def signout(request):
    """Signout"""
    logout(request)
    return redirect("auth:login")


@login_required
def profile(request):
    """The signed-in user's own account details."""
    form = ProfileForm(request.POST or None, instance=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('auth:profile')}?saved=1")

    return render(request, "authapp/profile.html", {"form": form})
