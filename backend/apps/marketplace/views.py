from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile
from apps.accounts.permissions import IsActiveAccount, IsCentralAdminWithPermission
from apps.audit.services import record_event
from apps.core.pagination import AdminListPagination
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country
from .models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory
from .permissions import IsPartnerOwner
from .serializers import (
    AuthorizationQueueSerializer,
    AuthorizationReviewSerializer,
    CatalogProductAdminSerializer,
    CatalogSearchSerializer,
    CatalogSellerAdminSerializer,
    MarketplaceAdminOptionsSerializer,
    ModerationRejectSerializer,
    PartnerAvailabilityUpdateSerializer,
    PartnerProductImageSerializer,
    ProductActionRequestSerializer,
    PartnerProductSerializer,
    PartnerSellerSerializer,
    PartnerStockUpdateSerializer,
    ProductPriceHistorySerializer,
    PublicCatalogListResponseSerializer,
    PublicCatalogProductSerializer,
    PublicCatalogSearchResponseSerializer,
    SellerOwnerAssignmentSerializer,
    SellerOwnerSerializer,
)
from .services import (
    approve_product,
    archive_product,
    assign_seller_owner,
    delete_product_image,
    reject_authorization,
    reject_product,
    reopen_authorization,
    set_primary_product_image,
    submit_product_for_review,
    verify_authorization,
)
from .validation import product_image_content_type


class PublicCatalogPagination(AdminListPagination):
    page_size = 12
    max_page_size = 24


def image_file_response(stream, filename, *, public=False):
    response = FileResponse(stream, content_type=product_image_content_type(filename))
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "public, max-age=300" if public else "private, no-store"
    return response


def image_schema_response(description="Fichier image"):
    return {200: OpenApiResponse(response=OpenApiTypes.BINARY, description=description)}


def verified_seller_filter():
    verified_pharmacy = Q(
        seller__kind=CatalogSeller.Kind.PHARMACY,
        seller__verification_status=CatalogSeller.VerificationStatus.VERIFIED,
        seller__professional_profile__verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
        seller__professional_profile__account__status="active",
        seller__professional_profile__account__user__is_active=True,
        seller__professional_profile__account__user__groups__name="professional_verified",
    )
    verified_supplier = Q(
        seller__kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
        seller__verification_status=CatalogSeller.VerificationStatus.VERIFIED,
        seller__verification_reference__gt="",
    )
    return Q(seller__is_active=True) & (verified_pharmacy | verified_supplier)


def public_products(product_type=None):
    query = CatalogProduct.objects.select_related(
        "seller", "seller__country", "seller__professional_profile__account__user",
    ).prefetch_related("images").filter(status=CatalogProduct.Status.PUBLISHED).filter(verified_seller_filter())
    if product_type:
        query = query.filter(product_type=product_type)
    verified_medicine = Q(
        product_type=CatalogProduct.ProductType.MEDICINE,
        authorization_status=CatalogProduct.AuthorizationStatus.VERIFIED,
        authorization_reference__gt="",
        authorization_verified_reference=F("authorization_reference"),
    )
    if product_type == CatalogProduct.ProductType.MEDICINE:
        return query.filter(verified_medicine)
    if product_type == CatalogProduct.ProductType.EQUIPMENT:
        return query
    return query.filter(Q(product_type=CatalogProduct.ProductType.EQUIPMENT) | verified_medicine)


def filtered_products(params, product_type=None):
    query = public_products(product_type)
    term = params.get("q", "").strip()
    if term:
        query = query.filter(
            Q(title__icontains=term) | Q(brand__icontains=term) | Q(active_ingredient__icontains=term)
            | Q(seller__name__icontains=term) | Q(seller__city__icontains=term)
            | Q(model_name__icontains=term) | Q(equipment_category__icontains=term)
        )
    if params.get("city"):
        query = query.filter(seller__city__icontains=params["city"].strip())
    if params.get("country"):
        query = query.filter(seller__country_id=params["country"])
    if params.get("min_price") is not None:
        query = query.filter(price_mga__gte=params["min_price"])
    if params.get("max_price") is not None:
        query = query.filter(price_mga__lte=params["max_price"])
    return query.distinct().order_by("-is_sponsored", "title")


class PublicCatalogQueryMixin:
    authentication_classes = ()
    permission_classes = (AllowAny,)
    pagination_class = PublicCatalogPagination

    def validated_query(self, request):
        serializer = CatalogSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def list_response(self, request, product_type):
        params = self.validated_query(request)
        queryset = filtered_products(params, product_type)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = PublicCatalogProductSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)


class PublicMedicineListView(PublicCatalogQueryMixin, APIView):
    @extend_schema(responses=PublicCatalogListResponseSerializer, summary="Lister les médicaments publics", tags=["Catalogue public"])
    def get(self, request):
        return self.list_response(request, CatalogProduct.ProductType.MEDICINE)


class PublicEquipmentListView(PublicCatalogQueryMixin, APIView):
    @extend_schema(responses=PublicCatalogListResponseSerializer, summary="Lister les matériels médicaux publics", tags=["Catalogue public"])
    def get(self, request):
        return self.list_response(request, CatalogProduct.ProductType.EQUIPMENT)


class PublicProductDetailView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=PublicCatalogProductSerializer, summary="Consulter une fiche produit publique", tags=["Catalogue public"])
    def get(self, request, slug):
        product = public_products().filter(slug=slug).distinct().first()
        if not product:
            raise Http404
        return Response(PublicCatalogProductSerializer(product, context={"request": request}).data)


class PublicProductImageView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=image_schema_response(), summary="Télécharger l’image principale publique d’un produit", tags=["Catalogue public"])
    def get(self, request, slug):
        product = public_products().filter(slug=slug).distinct().first()
        if not product or not product.image:
            raise Http404
        try:
            stream = product.image.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        return image_file_response(stream, product.image.name, public=True)


class PublicProductImageFileView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=image_schema_response(), summary="Télécharger une image de galerie publique", tags=["Catalogue public"])
    def get(self, request, slug, pk):
        product = public_products().filter(slug=slug).distinct().first()
        if not product:
            raise Http404
        image = get_object_or_404(ProductImage.objects.filter(product=product), pk=pk)
        try:
            stream = image.file.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        return image_file_response(stream, image.file.name, public=True)


class PublicCatalogSearchView(PublicCatalogQueryMixin, APIView):
    @extend_schema(responses=PublicCatalogSearchResponseSerializer, summary="Rechercher dans le catalogue public", tags=["Catalogue public"])
    def get(self, request):
        params = self.validated_query(request)
        term = params.get("q", "").strip()
        products = filtered_products(params) if term else public_products().none()
        products = list(products[:16])
        serializer = PublicCatalogProductSerializer(products, many=True, context={"request": request})
        return Response({
            "query": term,
            "products": serializer.data,
            "deferred_categories": ["pharmacies", "doctors", "specialists", "laboratories"],
            "message": "L’annuaire public des professionnels n’est pas encore ouvert.",
        })


class AdminMarketplaceMixin:
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = None

    def record(self, action, instance):
        record_event(actor=self.request.user, action=f"marketplace.{self.content_type}.{action}", target=instance, request=self.request)

    def perform_create(self, serializer):
        instance = serializer.save()
        self.record("created", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self.record("updated", instance)


class AdminCatalogSellerViewSet(AdminMarketplaceMixin, viewsets.ModelViewSet):
    serializer_class = CatalogSellerAdminSerializer
    queryset = CatalogSeller.objects.select_related("country", "professional_profile", "professional_profile__account__user")
    pagination_class = AdminListPagination
    content_type = "seller"
    http_method_names = ("get", "post", "patch", "delete", "head", "options")
    required_permission_by_action = {
        "list": "marketplace.view_catalogseller",
        "retrieve": "marketplace.view_catalogseller",
        "create": "marketplace.add_catalogseller",
        "update": "marketplace.change_catalogseller",
        "partial_update": "marketplace.change_catalogseller",
        "destroy": "marketplace.change_catalogseller",
    }

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.updated_by = self.request.user
        instance.save(update_fields=("is_active", "updated_by", "updated_at"))
        self.record("deactivated", instance)


class AdminCatalogProductViewSet(AdminMarketplaceMixin, viewsets.ModelViewSet):
    serializer_class = CatalogProductAdminSerializer
    queryset = CatalogProduct.objects.select_related("seller", "seller__country", "seller__professional_profile__account__user")
    pagination_class = AdminListPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    content_type = "product"
    http_method_names = ("get", "post", "patch", "delete", "head", "options")
    required_permission_by_action = {
        "list": "marketplace.view_catalogproduct",
        "retrieve": "marketplace.view_catalogproduct",
        "create": "marketplace.add_catalogproduct",
        "update": "marketplace.change_catalogproduct",
        "partial_update": "marketplace.change_catalogproduct",
        "destroy": "marketplace.change_catalogproduct",
    }

    def perform_destroy(self, instance):
        instance.status = CatalogProduct.Status.ARCHIVED
        instance.updated_by = self.request.user
        instance.save(update_fields=("status", "updated_by", "updated_at"))
        self.record("archived", instance)


class AdminMarketplaceOptionsView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "accounts.view_accountprofile"

    @extend_schema(responses=MarketplaceAdminOptionsSerializer, summary="Options d’administration du marketplace", tags=["Administration"])
    def get(self, request):
        pharmacies = ProfessionalProfile.objects.filter(category="pharmacy").select_related("country", "account__user").order_by("legal_name")
        accounts = AccountProfile.objects.filter(status=AccountProfile.Status.ACTIVE, user__is_active=True).select_related("user").order_by("user__username")

        def professional_summary(account):
            try:
                profile = account.professional_profile
            except ProfessionalProfile.DoesNotExist:
                return None, "", ""
            return profile.pk, profile.legal_name, profile.verification_status

        return Response({
            "countries": list(Country.objects.filter(is_active=True).order_by("name_fr").values("id", "name_fr")),
            "pharmacies": [{
                "id": profile.pk,
                "name": profile.legal_name,
                "city": profile.city,
                "verification_status": profile.verification_status,
                "is_active": bool(profile.account.status == "active" and profile.account.user.is_active),
                "eligible": bool(
                    profile.verification_status == ProfessionalProfile.VerificationStatus.APPROVED
                    and profile.account.status == AccountProfile.Status.ACTIVE
                    and profile.account.user.is_active
                    and profile.account.user.groups.filter(name="professional_verified").exists()
                ),
            } for profile in pharmacies],
            "accounts": [
                {
                    "id": account.pk,
                    "username": account.user.username,
                    "email": account.user.email,
                    "professional_profile": summary[0],
                    "professional_name": summary[1],
                    "professional_status": summary[2],
                }
                for account in accounts
                for summary in [professional_summary(account)]
            ],
        })


class AdminCatalogProductImageView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "marketplace.view_catalogproduct"

    @extend_schema(responses=image_schema_response("Image principale du produit"), summary="Télécharger l’image principale d’un produit", tags=["Administration"])
    def get(self, request, pk):
        product = CatalogProduct.objects.filter(pk=pk).first()
        if not product or not product.image:
            raise Http404
        try:
            stream = product.image.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        return image_file_response(stream, product.image.name)


def validation_detail(exc):
    return exc.message_dict if hasattr(exc, "message_dict") else exc.messages


class PartnerOwnedMixin:
    """Base des vues partenaires : identité du vendeur uniquement côté serveur."""

    permission_classes = (IsAuthenticated, IsActiveAccount, IsPartnerOwner)

    def partner_queryset(self, model):
        return model.objects.filter(seller=self.request.partner_seller)

    def owned_product(self, lookup="pk"):
        product = get_object_or_404(
            self.partner_queryset(CatalogProduct).select_related("seller"),
            pk=self.kwargs[lookup],
        )
        self.check_object_permissions(self.request, product)
        return product


class PartnerSellerDetailView(PartnerOwnedMixin, generics.RetrieveAPIView):
    serializer_class = PartnerSellerSerializer

    def get_queryset(self):
        return CatalogSeller.objects.filter(pk=self.request.partner_seller.pk)

    def get_object(self):
        seller = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, seller)
        return seller

    @extend_schema(summary="Consulter son vendeur attribué", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PartnerProductListView(PartnerOwnedMixin, generics.ListCreateAPIView):
    serializer_class = PartnerProductSerializer
    pagination_class = AdminListPagination

    def get_queryset(self):
        return self.partner_queryset(CatalogProduct).select_related("seller").order_by("-created_at")

    @extend_schema(summary="Lister les produits de son vendeur", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Créer un produit pour son vendeur", tags=["Espace partenaire"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PartnerProductDetailView(PartnerOwnedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PartnerProductSerializer

    def get_queryset(self):
        return self.partner_queryset(CatalogProduct).select_related("seller")

    def get_object(self):
        return self.owned_product()

    @extend_schema(summary="Consulter un produit de son vendeur", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Modifier un produit de son vendeur", tags=["Espace partenaire"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(summary="Archiver un produit de son vendeur", tags=["Espace partenaire"])
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_destroy(self, instance):
        archive_product(instance, actor=self.request.user, request=self.request)


class PartnerProductSubmitView(PartnerOwnedMixin, APIView):
    @extend_schema(request=ProductActionRequestSerializer, responses=PartnerProductSerializer, summary="Soumettre un produit à la modération", tags=["Espace partenaire"])
    def post(self, request, pk):
        product = self.owned_product()
        try:
            submit_product_for_review(product, actor=request.user, request=request)
        except DjangoValidationError as exc:
            raise ValidationError(validation_detail(exc)) from exc
        return Response(PartnerProductSerializer(product, context={"request": request}).data)


class PartnerDashboardView(PartnerOwnedMixin, APIView):
    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "products": {"type": "object"},
                    "orders": {"type": "object"},
                    "unread_notifications": {"type": "integer"},
                },
            }
        },
        summary="Indicateurs calculés sur le seul vendeur attribué",
        tags=["Espace partenaire"],
    )
    def get(self, request):
        seller = request.partner_seller
        products = CatalogProduct.objects.filter(seller=seller)
        orders = Order.objects.filter(seller=seller)
        return Response(
            {
                "seller_id": seller.pk,
                "products": {
                    "total": products.count(),
                    "draft": products.filter(status=CatalogProduct.Status.DRAFT).count(),
                    "published": products.filter(status=CatalogProduct.Status.PUBLISHED).count(),
                    "archived": products.filter(status=CatalogProduct.Status.ARCHIVED).count(),
                    "pending_moderation": products.filter(
                        moderation_status=CatalogProduct.ModerationStatus.PENDING
                    ).count(),
                },
                "orders": {
                    "total": orders.count(),
                    "awaiting_seller": orders.filter(status="awaiting_seller").count(),
                    "accepted": orders.filter(status="accepted").count(),
                    "preparing": orders.filter(status="preparing").count(),
                    "ready": orders.filter(status="ready").count(),
                    "completed": orders.filter(status="completed").count(),
                    "rejected": orders.filter(status="rejected").count(),
                    "cancelled": orders.filter(status="cancelled").count(),
                },
                "unread_notifications": Notification.objects.filter(
                    recipient=request.partner_owner_assignment.account, read_at__isnull=True
                ).count(),
            }
        )


class PartnerProductFieldUpdateView(PartnerOwnedMixin, APIView):
    request_serializer = None
    field_name = None
    summary = ""

    @extend_schema(request=PartnerStockUpdateSerializer, responses=PartnerProductSerializer, summary="Mettre à jour un champ produit", tags=["Espace partenaire"])
    def patch(self, request, pk):
        product = self.owned_product()
        serializer = self.request_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_serializer = PartnerProductSerializer(
            product,
            data=serializer.validated_data,
            partial=True,
            context={"request": request},
        )
        product_serializer.is_valid(raise_exception=True)
        return Response(PartnerProductSerializer(product_serializer.save(), context={"request": request}).data)


class PartnerProductStockView(PartnerProductFieldUpdateView):
    request_serializer = PartnerStockUpdateSerializer
    field_name = "stock_quantity"

    @extend_schema(
        request=PartnerStockUpdateSerializer,
        responses=PartnerProductSerializer,
        summary="Mettre à jour le stock réel d’un produit",
        tags=["Espace partenaire"],
    )
    def patch(self, request, pk):
        return super().patch(request, pk)


class PartnerProductAvailabilityView(PartnerProductFieldUpdateView):
    request_serializer = PartnerAvailabilityUpdateSerializer
    field_name = "availability"

    @extend_schema(
        request=PartnerAvailabilityUpdateSerializer,
        responses=PartnerProductSerializer,
        summary="Mettre à jour la disponibilité déclarative d’un produit",
        tags=["Espace partenaire"],
    )
    def patch(self, request, pk):
        return super().patch(request, pk)


class PartnerProductPriceHistoryView(PartnerOwnedMixin, generics.ListAPIView):
    serializer_class = ProductPriceHistorySerializer
    pagination_class = AdminListPagination

    def get_queryset(self):
        product = self.owned_product()
        return ProductPriceHistory.objects.filter(product=product).select_related("changed_by")

    @extend_schema(summary="Historique des prix d’un produit partenaire", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PartnerProductLegacyImageView(PartnerOwnedMixin, APIView):
    @extend_schema(responses=image_schema_response("Image principale historique du produit"), summary="Télécharger l’image principale historique d’un produit", tags=["Espace partenaire"])
    def get(self, request, pk):
        product = self.owned_product()
        if not product.image:
            raise Http404
        try:
            stream = product.image.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        return image_file_response(stream, product.image.name)


class PartnerProductImageView(PartnerOwnedMixin, generics.ListCreateAPIView):
    serializer_class = PartnerProductImageSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = AdminListPagination

    def get_product(self):
        return self.owned_product("product_pk")

    def get_queryset(self):
        return ProductImage.objects.filter(product=self.get_product()).select_related("product").order_by("sort_order", "created_at", "pk")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product"] = self.get_product()
        return context

    @extend_schema(summary="Lister les images d’un produit partenaire", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Ajouter une image privée à un produit", tags=["Espace partenaire"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PartnerProductImageDetailView(PartnerOwnedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PartnerProductImageSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_product(self):
        return self.owned_product("product_pk")

    def get_queryset(self):
        return ProductImage.objects.filter(product=self.get_product()).select_related("product")

    def get_object(self):
        image = super().get_object()
        self.check_object_permissions(self.request, image)
        return image

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product"] = self.get_product()
        return context

    def perform_destroy(self, instance):
        delete_product_image(instance, actor=self.request.user, request=self.request)

    @extend_schema(summary="Consulter une image privée d’un produit", tags=["Espace partenaire"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Modifier une image privée d’un produit", tags=["Espace partenaire"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(summary="Supprimer une image privée d’un produit", tags=["Espace partenaire"])
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class PartnerProductImageFileView(PartnerOwnedMixin, APIView):
    @extend_schema(responses=image_schema_response("Image privée du produit"), summary="Télécharger une image privée d’un produit", tags=["Espace partenaire"])
    def get(self, request, product_pk, pk):
        product = self.owned_product("product_pk")
        image = get_object_or_404(ProductImage.objects.filter(product=product), pk=pk)
        self.check_object_permissions(self.request, image)
        try:
            stream = image.file.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        return image_file_response(stream, image.file.name)


class PartnerProductImagePrimaryView(PartnerOwnedMixin, APIView):
    @extend_schema(request=ProductActionRequestSerializer, responses=PartnerProductImageSerializer, summary="Définir l’image principale d’un produit", tags=["Espace partenaire"])
    def post(self, request, product_pk, pk):
        product = self.owned_product("product_pk")
        image = get_object_or_404(ProductImage.objects.filter(product=product), pk=pk)
        self.check_object_permissions(self.request, image)
        set_primary_product_image(image, actor=request.user, request=request)
        return Response(PartnerProductImageSerializer(image, context={"request": request}).data)


class AdminModerationMixin:
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "marketplace.view_catalogproduct"

    def moderated_product(self):
        return get_object_or_404(
            CatalogProduct.objects.select_related("seller", "seller__professional_profile__account__user"),
            pk=self.kwargs["pk"],
        )


class AdminProductModerationListView(AdminModerationMixin, generics.ListAPIView):
    serializer_class = PartnerProductSerializer
    pagination_class = AdminListPagination

    def get_queryset(self):
        return CatalogProduct.objects.filter(
            moderation_status=CatalogProduct.ModerationStatus.PENDING
        ).select_related("seller").order_by("submitted_for_review_at", "pk")

    @extend_schema(summary="File de modération des produits", tags=["Administration"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminProductApproveView(AdminModerationMixin, APIView):
    required_permission = "marketplace.change_catalogproduct"

    @extend_schema(request=ProductActionRequestSerializer, responses=PartnerProductSerializer, summary="Approuver un produit soumis", tags=["Administration"])
    def post(self, request, pk):
        product = self.moderated_product()
        try:
            approve_product(product, actor=request.user, request=request)
        except DjangoValidationError as exc:
            raise ValidationError(validation_detail(exc)) from exc
        return Response(PartnerProductSerializer(product, context={"request": request}).data)


class AdminProductRejectView(AdminModerationMixin, APIView):
    required_permission = "marketplace.change_catalogproduct"

    @extend_schema(request=ModerationRejectSerializer, responses=PartnerProductSerializer, summary="Refuser un produit soumis", tags=["Administration"])
    def post(self, request, pk):
        product = self.moderated_product()
        serializer = ModerationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reject_product(
                product,
                actor=request.user,
                reason=serializer.validated_data["reason"],
                request=request,
            )
        except DjangoValidationError as exc:
            raise ValidationError(validation_detail(exc)) from exc
        return Response(PartnerProductSerializer(product, context={"request": request}).data)


class AdminAuthorizationQueueView(AdminModerationMixin, generics.ListAPIView):
    serializer_class = AuthorizationQueueSerializer
    pagination_class = AdminListPagination

    def get_queryset(self):
        return (
            CatalogProduct.objects.filter(
                product_type=CatalogProduct.ProductType.MEDICINE,
                authorization_reference__gt="",
                authorization_status__in=(
                    CatalogProduct.AuthorizationStatus.PENDING,
                    CatalogProduct.AuthorizationStatus.REJECTED,
                ),
            )
            .select_related("seller")
            .order_by("authorization_submitted_at", "pk")
        )

    @extend_schema(summary="File de vérification AMM", tags=["Administration"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminAuthorizationDecisionView(AdminModerationMixin, APIView):
    decision = None
    required_permission = "marketplace.change_catalogproduct"

    @extend_schema(request=AuthorizationReviewSerializer, responses=PartnerProductSerializer, summary="Décision administrative sur une AMM", tags=["Administration"])
    def post(self, request, pk):
        product = self.moderated_product()
        serializer = AuthorizationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            if self.decision == "verify":
                verify_authorization(product, actor=request.user, request=request)
            elif self.decision == "reject":
                reject_authorization(
                    product,
                    actor=request.user,
                    reason=serializer.validated_data.get("reason", ""),
                    request=request,
                )
            elif self.decision == "reopen":
                reopen_authorization(product, actor=request.user, request=request)
            else:  # pragma: no cover - garde-fou de configuration
                raise ValidationError({"decision": "Décision AMM inconnue."})
        except DjangoValidationError as exc:
            raise ValidationError(validation_detail(exc)) from exc
        return Response(PartnerProductSerializer(product, context={"request": request}).data)


class AdminProductPriceHistoryView(AdminModerationMixin, generics.ListAPIView):
    serializer_class = ProductPriceHistorySerializer
    pagination_class = AdminListPagination
    required_permission = "marketplace.view_productpricehistory"

    def get_queryset(self):
        product = self.moderated_product()
        return ProductPriceHistory.objects.filter(product=product).select_related("changed_by")

    @extend_schema(summary="Historique des prix d’un produit (administration)", tags=["Administration"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminSellerOwnerAssignmentView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "marketplace.change_catalogseller"

    @extend_schema(
        request=SellerOwnerAssignmentSerializer,
        responses=SellerOwnerSerializer,
        summary="Attribuer explicitement un vendeur existant à un compte partenaire",
        tags=["Administration"],
    )
    def post(self, request, pk):
        seller = get_object_or_404(CatalogSeller.objects.select_related("professional_profile"), pk=pk)
        serializer = SellerOwnerAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = assign_seller_owner(
                seller=seller,
                account=serializer.validated_data["account"],
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            raise ValidationError(validation_detail(exc)) from exc
        return Response(SellerOwnerSerializer(assignment, context={"request": request}).data, status=status.HTTP_201_CREATED)
