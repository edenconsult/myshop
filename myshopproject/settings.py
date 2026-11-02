import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project's .env file. override=True:
# shells that exported the old values (redis://localhost costs ~2s per new
# connection because Redis binds IPv4 only) must not outrank the file
load_dotenv(BASE_DIR / ".env", override=True)

env = os.environ.get


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-##6#&ge+^*l%o&t9n8agdapve7)iyfobn93+zcpi-3xu+j&#hl")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DJANGO_DEBUG", default="True") == "True"

ALLOWED_HOSTS = []
# ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOWED_ORIGINS = [
#     "http://127.0.0.1",
# ]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django_browser_reload",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "corsheaders",
    "widget_tweaks",
    "django_htmx",
    "django_extensions",
    "compressor",
    "authapp",
    "core",
    "celery_progress",
    "wkhtmltopdf",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

ROOT_URLCONF = "myshopproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myshopproject.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="myshopproject"),
        "USER": env("POSTGRES_USER", default="postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        # reuse connections between requests instead of reconnecting each time
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "productionfiles"
# The one source tree: Tailwind and the icon sprite build into static/, and
# collectstatic copies from here into STATIC_ROOT above.
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

COMPRESS_ROOT = BASE_DIR / "productionfiles"
# Only compress for a real deployment. In development the raw static/src/output.css
# is served, so a Tailwind rebuild shows up without running collectstatic first.
COMPRESS_ENABLED = not DEBUG
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)

# AUTHENTICATION SETTINGS
AUTH_USER_MODEL = "authapp.Account"
LOGIN_URL = "auth:login"
LOGIN_REDIRECT_URL = "auth:login_success"
LOGOUT_REDIRECT_URL = "auth:login"


# Celery settings
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379")

# Printed documents (receipts, reports) read their company block from here.
# Empty email/footer simply drop their line from the printout.
COMPANY_INFO = {
    "name": env("COMPANY_NAME", default="Noble Cosmetics Ltd."),
    "location": env("COMPANY_LOCATION", default="Atebubu Bayere Bode Junction"),
    "phone": env("COMPANY_PHONE", default="+233 24 833 1063"),
    "email": env("COMPANY_EMAIL", default=""),
    "footer": env("COMPANY_FOOTER", default="Goods sold are not returnable. Thank you for your patronage!"),
    "developer": env("COMPANY_DEVELOPER", default="Eden"),
}
