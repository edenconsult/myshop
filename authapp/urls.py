from django.urls import path
from . import views

app_name = 'auth'
urlpatterns = [
    path('login/', views.signin, name="login"),
    path('login_success/', views.login_success, name="login_success"),
    path('logout', views.signout, name="logout"),
]
