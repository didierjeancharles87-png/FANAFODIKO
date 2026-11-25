import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR.parent / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key")
def env_flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def env_list(name, default=""):
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


DEBUG = env_flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
INSTALLED_APPS = ["config.admin.FanafodikoAdminConfig", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "rest_framework", "corsheaders", "drf_spectacular", "apps.core", "apps.reference", "apps.audit", "apps.accounts", "apps.professionals", "apps.sitecontent", "apps.marketplace", "apps.orders", "apps.notifications", "apps.promotions"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("DATABASE_NAME", "fanafodiko_db"), "USER": os.getenv("DATABASE_USER", "fanafodiko_user"), "PASSWORD": os.getenv("DATABASE_PASSWORD", ""), "HOST": os.getenv("DATABASE_HOST", "127.0.0.1"), "PORT": os.getenv("DATABASE_PORT", "5432"), "CONN_MAX_AGE": 60}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": f"django.contrib.auth.password_validation.{name}"} for name in ("UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator")]
LANGUAGE_CODE = "fr-fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
TIME_ZONE = "Indian/Antananarivo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "private_media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated", "apps.accounts.permissions.IsActiveAccount"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "NUM_PROXIES": env_int("DJANGO_NUM_PROXIES", 0),
    # Limites par portée : IP puis compte/adresse e-mail quand elle est connue.
    "DEFAULT_THROTTLE_RATES": {
        "login_ip": os.getenv("THROTTLE_LOGIN_IP", "20/m"),
        "login_account": os.getenv("THROTTLE_LOGIN_ACCOUNT", "5/m"),
        "register_ip": os.getenv("THROTTLE_REGISTER_IP", "10/h"),
        "register_account": os.getenv("THROTTLE_REGISTER_ACCOUNT", "3/h"),
        "csrf_ip": os.getenv("THROTTLE_CSRF_IP", "60/m"),
        "coupon_ip": os.getenv("THROTTLE_COUPON_IP", "30/m"),
        "coupon_account": os.getenv("THROTTLE_COUPON_ACCOUNT", "10/m"),
    },
}
SPECTACULAR_SETTINGS = {
    "TITLE": "FANAFODIKO API",
    "DESCRIPTION": "Socle API de FANAFODIKO",
    "VERSION": "0.3.0",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "ProfessionalCategoryEnum": "apps.accounts.categories.ProfessionalCategory",
        "VerificationCategoryEnum": "apps.accounts.models.ProfessionalVerificationRequest.Category",
        "AccountStatusEnum": "apps.accounts.models.AccountProfile.Status",
        "ProfessionalVerificationStatusEnum": "apps.accounts.models.ProfessionalVerificationRequest.Status",
        "CatalogSellerVerificationStatusEnum": "apps.marketplace.models.CatalogSeller.VerificationStatus",
        "CatalogProductStatusEnum": "apps.marketplace.models.CatalogProduct.Status",
        "CatalogProductAuthorizationStatusEnum": "apps.marketplace.models.CatalogProduct.AuthorizationStatus",
        "CatalogProductAvailabilityEnum": "apps.marketplace.models.CatalogProduct.Availability",
        "CatalogProductModerationStatusEnum": "apps.marketplace.models.CatalogProduct.ModerationStatus",
        "CatalogProductProductTypeEnum": "apps.marketplace.models.CatalogProduct.ProductType",
        "CatalogProductEquipmentCategoryEnum": "apps.marketplace.models.CatalogProduct.EquipmentCategory",
        "CatalogSellerKindEnum": "apps.marketplace.models.CatalogSeller.Kind",
        "ProfessionalProfileVerificationStatusEnum": "apps.professionals.models.ProfessionalProfile.VerificationStatus",
        "ProfessionalDocumentReviewStatusEnum": "apps.professionals.models.ProfessionalDocument.ReviewStatus",
        "OrderStatusEnum": "apps.orders.models.OrderStatus",
        "PromotionStatusEnum": "apps.promotions.models.PromotionStatus",
        "DiscountTypeEnum": "apps.promotions.models.DiscountType",
        "NotificationTypeEnum": "apps.notifications.models.NotificationType",
        "SiteImageSlotEnum": "apps.sitecontent.models.SiteImage.Slot",
        "PageContentPageEnum": "apps.sitecontent.models.PageContent.Page",
    },
}
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
