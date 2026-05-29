"""
Django settings for config project.
"""

from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================
# SECURITY
# =========================

SECRET_KEY = "django-insecure-your-secret-key-here"

DEBUG = True

ALLOWED_HOSTS = []


# =========================
# APPLICATIONS
# =========================

INSTALLED_APPS = [
    "jazzmin",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "patients.apps.PatientsConfig",
    "dashboard",
    "website.apps.WebsiteConfig",
]

# =========================
# MIDDLEWARE
# =========================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "dashboard.middleware.AdminAccessMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =========================
# URL / TEMPLATE / WSGI
# =========================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "website" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context_processors.dashboard_notifications",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


# =========================
# DATABASE
# =========================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# =========================
# PASSWORD VALIDATION
# =========================

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


# =========================
# INTERNATIONALIZATION
# =========================

LANGUAGE_CODE = "uz"

LANGUAGES = [
    ("uz", _("O‘zbek")),
    ("ru", _("Русский")),
    ("en", _("English")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "Asia/Tashkent"

USE_I18N = True

USE_TZ = True


# =========================
# STATIC FILES
# =========================

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# =========================
# JAZZMIN SETTINGS
# =========================

JAZZMIN_SETTINGS = {
    "site_title": _("Veterinariya tizimi"),
    "site_header": _("Veterinariya klinikasi"),
    "site_brand": _("VetClinic Admin"),
    "welcome_sign": _("Veterinariya klinikasi boshqaruv paneliga xush kelibsiz"),
    "copyright": "VetClinic",

    "show_sidebar": True,
    "navigation_expanded": True,
    "language_chooser": True,

    # MUHIM: fayl nomlari aynan shunday bo‘lsin
    # static/css/custom_admin.css
    # static/js/custom_admin.js
    "custom_css": "css/custom_admin_modern.css",
    "custom_js": "js/custom_admin_modern.js",

    "icons": {
        "auth.User": "fas fa-user",
        "auth.Group": "fas fa-users-cog",

        "patients.Owner": "fas fa-user",
        "patients.Pet": "fas fa-paw",
        "patients.Visit": "fas fa-notes-medical",
        "patients.MyVisit": "fas fa-clipboard-list",
        "patients.DoctorProfile": "fas fa-user-md",
        "patients.NewPatient": "fas fa-user-plus",
    },

    "order_with_respect_to": [
        "patients.NewPatient",
        "patients.Visit",
        "patients.MyVisit",
        "patients.Owner",
        "patients.Pet",
        "patients.DoctorProfile",
        "auth.User",
        "auth.Group",
    ],
}


# =========================
# JAZZMIN UI TWEAKS
# =========================

JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",

    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",
    "brand_colour": "navbar-primary",

    "accent": "accent-info",

    "button_classes": {
        "primary": "btn btn-info",
        "secondary": "btn btn-secondary",
        "info": "btn btn-info",
        "warning": "btn btn-warning",
        "danger": "btn btn-danger",
        "success": "btn btn-success",
    },

    "body_small_text": False,
    "navbar_small_text": False,
    "sidebar_nav_small_text": False,
    "footer_small_text": False,

    "sidebar_nav_flat_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_compact_style": False,

    "brand_small_text": False,
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard_home"
LOGOUT_REDIRECT_URL = "login"