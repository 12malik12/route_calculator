"""Django settings for the TruckLogix project."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# `.env.development.local` at the repo root; we also support a local backend .env.
for _env_file in (
    REPO_ROOT / ".env.development.local",
    REPO_ROOT / ".env.local",
    REPO_ROOT / ".env",
    BASE_DIR / ".env",
):
    if _env_file.exists():
        load_dotenv(_env_file, override=False)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-insecure-key-change-me-in-production"
)

# Render environment should have DJANGO_DEBUG set to 0
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Dynamically updates based on whether you are running locally or on Render
if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [".onrender.com", "localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "trucklogix.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "trucklogix.wsgi.application"

# A database is required by Django even though this app stores no data.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Static files settings
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # <-- ADDED THIS TO FIX THE RENDER BUILD ERROR

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS configuration: secure it for production, leave open for local Vite dev
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        "https://route-calculator-5896-heo6nwtmd-47tesfayewk-8191s-projects.vercel.app/",  # FIXME: Replace with your actual live Vercel domain
    ]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

# OpenRouteService API key (https://openrouteservice.org/dev/#/signup)
ORS_API_KEY = os.environ.get("ORS_API_KEY", "")