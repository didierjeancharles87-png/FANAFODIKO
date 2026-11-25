"""Seed clearly labelled demonstration data in the isolated local SQLite database.

The command refuses to run against PostgreSQL or any non-test settings module.
It never touches the real FANAFODIKO database.
"""

import base64
import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile, ProfessionalVerificationRequest
from apps.marketplace.models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory, SellerOwner
from apps.professionals.models import (
    PharmacyDetails,
    PractitionerDetails,
    ProfessionalDocument,
    ProfessionalProfile,
)
from apps.reference.models import Country
from apps.sitecontent.models import SiteConfiguration

User = get_user_model()

# 1x1 transparent PNG used only as a local test asset.
DEMO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
DEMO_AMM = "DEMO-AMM-NON-VALABLE-001"


class Command(BaseCommand):
    help = "Create isolated, clearly labelled local demonstration data (SQLite test settings only)."

    def handle(self, *args, **options):
        settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "")
        database = settings.DATABASES.get("default", {})
        if "local_test" not in settings_module and settings_module != "config.settings.test":
            raise CommandError("Refus : utilisez DJANGO_SETTINGS_MODULE=config.settings.local_test ou config.settings.test.")
        if database.get("ENGINE") != "django.db.backends.sqlite3":
            raise CommandError("Refus : la base active n’est pas SQLite. Aucune donnée n’a été créée.")
        if settings_module == "config.settings.test" and database.get("NAME") == ":memory:":
            raise CommandError("Refus : la base de test en mémoire ne peut pas être partagée avec un serveur local.")

        with transaction.atomic():
            admin = self._user("admin.demo", "AdminDemo123!", "admin@example.test", is_staff=True, is_superuser=True)
            patient = self._user("patient.demo", "PatientDemo123!", "patient@example.test")
            pending = self._user("pending.demo", "PendingDemo123!", "pending@example.test")
            pharmacist = self._user("pharmacie.demo", "PharmacieDemo123!", "pharmacie@example.test")
            supplier = self._user("fournisseur.demo", "FournisseurDemo123!", "fournisseur@example.test")
            other = self._user("autre.demo", "AutreDemo123!", "autre@example.test")

            self._add_group(patient, "patient")
            self._add_group(pending, "professional_pending")
            for user in (pharmacist,):
                self._add_group(user, "professional_pending")
                self._add_group(user, "professional_verified")
            self._add_group(supplier, "patient")
            self._add_group(other, "patient")

            country = Country.objects.get(code_alpha2="MG")

            pending_request, _ = ProfessionalVerificationRequest.objects.get_or_create(
                user=pending,
                defaults={
                    "category": ProfessionalVerificationRequest.Category.DOCTOR,
                    "organization_name": "TEST – Cabinet médical de démonstration",
                    "license_number": "TEST-MED-001",
                    "country": country,
                    "status": ProfessionalVerificationRequest.Status.PENDING,
                },
            )
            pending_profile, _ = ProfessionalProfile.objects.get_or_create(
                account=pending.account_profile,
                defaults={
                    "category": ProfessionalCategory.DOCTOR,
                    "legal_name": "TEST – Dr Démonstration",
                    "manager_name": "Dr Démonstration",
                    "contact_phone": "+261380000001",
                    "contact_email": "pending@example.test",
                    "country": country,
                    "region": "Analamanga",
                    "city": "Antananarivo",
                    "address": "1 rue du Test, Antananarivo",
                    "verification_status": ProfessionalProfile.VerificationStatus.PENDING,
                    "verification_request": pending_request,
                },
            )
            PractitionerDetails.objects.get_or_create(
                profile=pending_profile,
                defaults={
                    "specialty": "Médecine générale (démonstration)",
                    "registration_number": "TEST-MED-001",
                    "establishment_name": "Cabinet de démonstration",
                    "availability_info": "Données de test — aucun service réel.",
                },
            )
            self._document(pending_profile, "test-medical-license.txt", "license")

            approved_request, _ = ProfessionalVerificationRequest.objects.get_or_create(
                user=pharmacist,
                defaults={
                    "category": ProfessionalVerificationRequest.Category.PHARMACY,
                    "organization_name": "TEST – Pharmacie de démonstration",
                    "license_number": "TEST-PHARM-001",
                    "country": country,
                    "status": ProfessionalVerificationRequest.Status.APPROVED,
                    "reviewed_by": admin,
                    "reviewed_at": timezone.now(),
                    "review_notes": "Données de test — validation simulée.",
                },
            )
            pharmacy_profile, _ = ProfessionalProfile.objects.get_or_create(
                account=pharmacist.account_profile,
                defaults={
                    "category": ProfessionalCategory.PHARMACY,
                    "legal_name": "TEST – Pharmacie de démonstration",
                    "manager_name": "Pharmacien de test",
                    "contact_phone": "+261380000002",
                    "contact_email": "pharmacie@example.test",
                    "country": country,
                    "region": "Analamanga",
                    "city": "Antananarivo",
                    "address": "2 rue du Test, Antananarivo",
                    "verification_status": ProfessionalProfile.VerificationStatus.APPROVED,
                    "verification_request": approved_request,
                },
            )
            PharmacyDetails.objects.get_or_create(
                profile=pharmacy_profile,
                defaults={
                    "commercial_name": "Pharmacie Test FANAFODIKO",
                    "license_number": "TEST-PHARM-001",
                    "opening_hours": {"lundi": "08:00-17:00"},
                },
            )
            self._document(pharmacy_profile, "test-pharmacy-license.txt", "license")

            pharmacy_seller, _ = CatalogSeller.objects.get_or_create(
                name="TEST – Pharmacie de démonstration",
                defaults={
                    "kind": CatalogSeller.Kind.PHARMACY,
                    "professional_profile": pharmacy_profile,
                    "country": country,
                    "region": "Analamanga",
                    "city": "Antananarivo",
                    "verification_status": CatalogSeller.VerificationStatus.VERIFIED,
                    "verification_reference": "TEST-PHARM-001",
                    "created_by": admin,
                    "updated_by": admin,
                },
            )
            supplier_seller, _ = CatalogSeller.objects.get_or_create(
                name="TEST – Fournisseur de démonstration",
                defaults={
                    "kind": CatalogSeller.Kind.MEDICAL_SUPPLIER,
                    "country": country,
                    "region": "Analamanga",
                    "city": "Antananarivo",
                    "verification_status": CatalogSeller.VerificationStatus.VERIFIED,
                    "verification_reference": "TEST-FOURNISSEUR-001",
                    "created_by": admin,
                    "updated_by": admin,
                },
            )
            other_seller, _ = CatalogSeller.objects.get_or_create(
                name="TEST – Autre vendeur de démonstration",
                defaults={
                    "kind": CatalogSeller.Kind.MEDICAL_SUPPLIER,
                    "country": country,
                    "region": "Analamanga",
                    "city": "Antananarivo",
                    "verification_status": CatalogSeller.VerificationStatus.VERIFIED,
                    "verification_reference": "TEST-FOURNISSEUR-002",
                    "created_by": admin,
                    "updated_by": admin,
                },
            )
            for account, seller in (
                (pharmacist.account_profile, pharmacy_seller),
                (supplier.account_profile, supplier_seller),
                (other.account_profile, other_seller),
            ):
                SellerOwner.objects.get_or_create(
                    account=account,
                    seller=seller,
                    defaults={"created_by": admin, "updated_by": admin},
                )

            gloves = self._product(
                title="TEST – Gants d’examen (démonstration)",
                seller=supplier_seller,
                product_type=CatalogProduct.ProductType.EQUIPMENT,
                price=Decimal("1500.00"),
                availability=CatalogProduct.Availability.AVAILABLE,
                stock=12,
                status=CatalogProduct.Status.PUBLISHED,
                moderation=CatalogProduct.ModerationStatus.APPROVED,
                admin=admin,
                actor=supplier,
                description="Donnée de test. Produit fictif, non destiné à la vente réelle.",
                equipment_category=CatalogProduct.EquipmentCategory.PROTECTION,
                technical_specifications={"usage": "démonstration uniquement", "taille": "M"},
            )
            medicine = self._product(
                title="TEST – Paracétamol 500 mg (démonstration, non disponible)",
                seller=pharmacy_seller,
                product_type=CatalogProduct.ProductType.MEDICINE,
                price=Decimal("2500.00"),
                availability=CatalogProduct.Availability.UNAVAILABLE,
                stock=None,
                status=CatalogProduct.Status.DRAFT,
                moderation=CatalogProduct.ModerationStatus.PENDING,
                admin=admin,
                actor=pharmacist,
                description="Fiche de démonstration. Médicament fictif, non réellement disponible.",
                active_ingredient="Paracétamol (donnée de test)",
                dosage="500 mg (démonstration)",
                pharmaceutical_form="Comprimé fictif",
                packaging="Boîte de test",
                requires_prescription=True,
                authorization_status=CatalogProduct.AuthorizationStatus.VERIFIED,
                authorization_reference=DEMO_AMM,
            )
            self._product(
                title="TEST – Stéthoscope de démonstration (autre vendeur)",
                seller=other_seller,
                product_type=CatalogProduct.ProductType.EQUIPMENT,
                price=Decimal("25000.00"),
                availability=CatalogProduct.Availability.AVAILABLE,
                stock=3,
                status=CatalogProduct.Status.PUBLISHED,
                moderation=CatalogProduct.ModerationStatus.APPROVED,
                admin=admin,
                actor=other,
                description="Donnée de test appartenant à un autre vendeur ; sert à vérifier l’isolement.",
                equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
                technical_specifications={"usage": "test d’isolement uniquement"},
            )
            self._image(gloves, supplier)
            self._image(medicine, pharmacist)

            SiteConfiguration.objects.update_or_create(
                pk=1,
                defaults={
                    "whatsapp_number": "+261 38 16 27 248",
                    "updated_by": admin,
                },
            )

        self.stdout.write(self.style.SUCCESS("Données de démonstration locales créées dans la base SQLite isolée."))
        self.stdout.write("Comptes de test (mot de passe indiqué pour chaque ligne) :")
        for username, password in (
            ("admin.demo", "AdminDemo123!"),
            ("patient.demo", "PatientDemo123!"),
            ("pending.demo", "PendingDemo123!"),
            ("pharmacie.demo", "PharmacieDemo123!"),
            ("fournisseur.demo", "FournisseurDemo123!"),
            ("autre.demo", "AutreDemo123!"),
        ):
            self.stdout.write(f"  {username} / {password}")
        self.stdout.write("Toutes les fiches sont préfixées « TEST – » et ne représentent pas des produits réellement disponibles.")

    @staticmethod
    def _user(username, password, email, is_staff=False, is_superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser, "is_active": True},
        )
        user.email = email
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = True
        user.set_password(password)
        user.save()
        AccountProfile.objects.get_or_create(user=user)
        return user

    @staticmethod
    def _add_group(user, name):
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)

    @staticmethod
    def _document(profile, filename, document_type):
        if profile.documents.exists():
            return
        document = ProfessionalDocument(
            profile=profile,
            document_type=document_type,
            original_filename=filename,
            content_type="text/plain",
            size_bytes=24,
            review_status=ProfessionalDocument.ReviewStatus.ACCEPTED,
        )
        document.file.save(filename, ContentFile(b"DOCUMENT DE TEST - FANAFODIKO"), save=False)
        document.save()

    @staticmethod
    def _product(
        *,
        title,
        seller,
        product_type,
        price,
        availability,
        stock,
        status,
        moderation,
        admin,
        actor,
        description,
        equipment_category="",
        technical_specifications=None,
        active_ingredient="",
        dosage="",
        pharmaceutical_form="",
        packaging="",
        requires_prescription=True,
        authorization_status=CatalogProduct.AuthorizationStatus.PENDING,
        authorization_reference="",
    ):
        now = timezone.now()
        clean_reference = (authorization_reference or "").strip()
        verified_reference = (
            clean_reference
            if authorization_status == CatalogProduct.AuthorizationStatus.VERIFIED
            else ""
        )
        product, created = CatalogProduct.objects.get_or_create(
            title=title,
            seller=seller,
            defaults={
                "product_type": product_type,
                "description": description,
                "price_mga": price,
                "availability": availability,
                "status": status,
                "moderation_status": moderation,
                "submitted_for_review_at": now if moderation == CatalogProduct.ModerationStatus.PENDING else None,
                "reviewed_by": admin if moderation == CatalogProduct.ModerationStatus.APPROVED else None,
                "reviewed_at": now if moderation == CatalogProduct.ModerationStatus.APPROVED else None,
                "review_notes": "Données de test — modération simulée." if moderation == CatalogProduct.ModerationStatus.APPROVED else "",
                "stock_quantity": stock,
                "stock_updated_at": now if stock is not None else None,
                "equipment_category": equipment_category,
                "technical_specifications": technical_specifications or {},
                "active_ingredient": active_ingredient,
                "dosage": dosage,
                "pharmaceutical_form": pharmaceutical_form,
                "packaging": packaging,
                "requires_prescription": requires_prescription,
                "authorization_status": authorization_status,
                "authorization_reference": clean_reference,
                "authorization_submitted_at": now if clean_reference else None,
                "authorization_verified_reference": verified_reference,
                "authorization_reviewed_by": admin if verified_reference else None,
                "authorization_reviewed_at": now if verified_reference else None,
                "authorization_decision_tracked": bool(verified_reference),
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if created:
            try:
                product.full_clean()
            except ValidationError as exc:
                raise CommandError(f"Fiche de démonstration invalide ({title}) : {exc}") from exc
            product.save()
            ProductPriceHistory.objects.get_or_create(
                product=product,
                price_mga=price,
                changed_by=actor,
                defaults={"reason": "Prix initial de démonstration."},
            )
        return product

    @staticmethod
    def _image(product, actor):
        if product.images.exists():
            return
        image = ProductImage(
            product=product,
            alt_text=f"Image de test — {product.title}",
            sort_order=0,
            is_primary=True,
            uploaded_by=actor,
        )
        image.file.save("demo-product.png", ContentFile(DEMO_PNG), save=False)
        image.save()
