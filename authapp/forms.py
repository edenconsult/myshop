from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django import forms

# same control shell the product dialog uses, kept here so authapp does not
# depend on core
FIELD = (
    "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm "
    "text-slate-900 transition-colors placeholder:text-slate-400 "
    "focus:border-emerald-500 focus:bg-white focus:outline-none "
    "focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 "
    "dark:bg-slate-950 dark:text-slate-100 dark:focus:bg-slate-900"
)


class NewAccountForm(UserCreationForm):
    """The owner creates salespersons only — user_type is set in save(), never
    taken from the request, so a forged role field cannot open an admin seat."""

    # declared rather than left to Meta.fields so the owner must type both
    # names; the length cap comes from the model, which validates the instance
    first_name = forms.CharField()
    last_name = forms.CharField()

    class Meta:
        model = get_user_model()
        # the names must be listed here as well as declared above: Django's
        # construct_instance skips any model field missing from Meta.fields,
        # which is how typed names used to vanish before the account was saved
        fields = ["username", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": FIELD})

    def save(self, commit=True):
        account = super().save(commit=False)
        account.user_type = "SALEPERSON"
        if commit:
            account.save()
        return account


class AccountSetPasswordForm(forms.Form):
    """Owner-side password reset: two entries, checked against the project's
    validators, with no knowledge of the old password."""

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": FIELD, "autocomplete": "new-password"}),
        label="New password",
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": FIELD, "autocomplete": "new-password"}),
        label="Confirm password",
    )

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("new_password1")
        password2 = cleaned.get("new_password2")
        if password1 and password2:
            if password1 != password2:
                raise ValidationError("The two password entries do not match.")
            validate_password(password1)
        return cleaned


class ProfileForm(forms.ModelForm):
    """The four editable facts about an account: two names, a phone, an email.

    Used by the owner for someone else and by everyone for themselves. username
    and user_type stay out on purpose: the login handle and the role that gates
    the whole app are not editable here, by anyone, including the owner.
    """

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "email", "telephone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": FIELD}),
            "last_name": forms.TextInput(attrs={"class": FIELD}),
            "email": forms.EmailInput(attrs={"class": FIELD}),
            "telephone": forms.TextInput(attrs={"class": FIELD}),
        }


def profile_form_for(account, data=None):
    """A ProfileForm for one roster row.

    The auto_id suffix is what keeps field ids unique now that the accounts
    page carries a dialog per row; the field names stay unprefixed so the POST
    body is the plain one the view and the tests read.
    """
    return ProfileForm(data, instance=account, auto_id=f"id_edit_{account.pk}_%s")


class PasswordChangeForm(DjangoPasswordChangeForm):
    """Django's form, which already verifies the old password and runs the
    project's AUTH_PASSWORD_VALIDATORS; only the control styling is ours."""

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in ("old_password", "new_password1", "new_password2"):
            self.fields[field].widget.attrs.update({"class": FIELD})
