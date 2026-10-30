from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from utils import is_admin


def signin(request):
    """Signin"""
    if request.user.is_authenticated and request.user.user_type == 'ADMIN':
        return redirect('core:base')
    elif request.user.is_authenticated and request.user.user_type == 'SALEPERSON':
        return redirect('sales:base')

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
    if request.user.user_type == "ADMIN":
        return redirect("core:base")
    elif request.user.user_type == "SALEPERSON":
        return redirect("sales:base")
    else:
        return HttpResponse(b"Unauthorized Access.")


@login_required
def signout(request):
    """Signout"""
    logout(request)
    return redirect("auth:login")
