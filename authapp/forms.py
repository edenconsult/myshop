from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms


class NewAccountForm(UserCreationForm):
    first_name = forms.CharField()
    last_name = forms.CharField()
    other_name = forms.CharField(required=False)

    class Meta:
        model = get_user_model()
        fields = ["username", "password1", "password2"]
