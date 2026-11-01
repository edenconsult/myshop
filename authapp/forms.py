from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserCreationForm
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
    first_name = forms.CharField()
    last_name = forms.CharField()
    other_name = forms.CharField(required=False)

    class Meta:
        model = get_user_model()
        fields = ["username", "password1", "password2"]


class ProfileForm(forms.ModelForm):
    """What a signed-in user is allowed to change about their own account.

    username and user_type stay out on purpose: the login handle and the role
    that gates the whole app are not self-service.
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


class PasswordChangeForm(DjangoPasswordChangeForm):
    """Django's form, which already verifies the old password and runs the
    project's AUTH_PASSWORD_VALIDATORS; only the control styling is ours."""

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in ("old_password", "new_password1", "new_password2"):
            self.fields[field].widget.attrs.update({"class": FIELD})
