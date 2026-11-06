from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views
from .forms import PasswordChangeForm

app_name = 'auth'
urlpatterns = [
    path('login/', views.signin, name="login"),
    path('login_success/', views.login_success, name="login_success"),
    path('accounts/', views.accounts, name="accounts"),
    path('accounts/create/', views.account_create, name="account-create"),
    path(
        'accounts/<uuid:account_id>/update-details/',
        views.account_update_details,
        name="account-update-details",
    ),
    path(
        'accounts/<uuid:account_id>/reset-password/',
        views.account_reset_password,
        name="account-reset-password",
    ),
    path(
        'accounts/<uuid:account_id>/toggle-active/',
        views.account_toggle_active,
        name="account-toggle-active",
    ),
    path('profile/', views.profile, name="profile"),
    path(
        'password/change/',
        auth_views.PasswordChangeView.as_view(
            template_name="authapp/password_change.html",
            form_class=PasswordChangeForm,
            success_url=reverse_lazy("auth:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        'password/change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name="authapp/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path('logout', views.signout, name="logout"),
]
