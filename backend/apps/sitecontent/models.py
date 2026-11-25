from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class SiteConfiguration(models.Model):
    whatsapp_number = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_config_updates")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Configuration du site"


class FAQEntry(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField(max_length=5000)
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.question


class NewsArticle(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.CharField(max_length=400)
    body = models.TextField(max_length=12000)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_news_created")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-id")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        elif not self.is_published:
            self.published_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class PageContent(models.Model):
    class Page(models.TextChoices):
        HOME = "home", "Accueil"
        ABOUT = "about", "À propos"
        CONTACT = "contact", "Contact"
        TERMS = "terms", "Conditions"
        PRIVACY = "privacy", "Confidentialité"

    page = models.CharField(max_length=16, choices=Page.choices, unique=True)
    title = models.CharField(max_length=200)
    introduction = models.CharField(max_length=600, blank=True)
    body = models.TextField(max_length=12000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_pages_updated")

    class Meta:
        ordering = ("page",)

    def __str__(self):
        return self.get_page_display()


class SiteImage(models.Model):
    class Slot(models.TextChoices):
        TELECONSULTATION = "teleconsultation", "Téléconsultation"
        PHARMACY = "pharmacy", "Pharmacie"
        LABORATORY = "laboratory", "Laboratoire"
        DENTISTRY = "dentistry", "Soins dentaires"
        SPECIALIST = "specialist", "Médecins et spécialistes"

    slot = models.CharField(max_length=24, choices=Slot.choices, unique=True)
    image = models.FileField(upload_to="site_assets/", blank=True, validators=[FileExtensionValidator(("jpg", "jpeg", "png", "webp"))])
    alt_text = models.CharField(max_length=240)
    is_visible = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_images_updated")

    class Meta:
        ordering = ("slot",)

    def __str__(self):
        return self.get_slot_display()
