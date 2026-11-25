from django.http import FileResponse, Http404
from pathlib import Path
from drf_spectacular.utils import OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAccount, IsCentralAdminWithPermission
from apps.audit.services import record_event
from .models import FAQEntry, NewsArticle, PageContent, SiteConfiguration, SiteImage
from .serializers import (
    FAQEntrySerializer,
    NewsArticleSerializer,
    PageContentSerializer,
    PublicFAQResponseSerializer,
    PublicSiteImageListResponseSerializer,
    SiteConfigurationResponseSerializer,
    SiteConfigurationSerializer,
    SiteImageSerializer,
)


def image_schema_response():
    return {200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Fichier image")}


class AdminContentMixin:
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = None

    def perform_create(self, serializer):
        obj = serializer.save()
        record_event(actor=self.request.user, action=f"site_content.{self.content_type}.created", target=obj, request=self.request)

    def perform_update(self, serializer):
        obj = serializer.save()
        record_event(actor=self.request.user, action=f"site_content.{self.content_type}.updated", target=obj, request=self.request)

    def perform_destroy(self, instance):
        pk = instance.pk
        target = instance
        if isinstance(instance, SiteImage):
            if instance.image:
                instance.image.delete(save=False)
            instance.image = ""
            instance.is_visible = False
            instance.save(update_fields=("image", "is_visible", "updated_at"))
        else:
            instance.delete()
            target.pk = pk
        record_event(actor=self.request.user, action=f"site_content.{self.content_type}.deleted", target=target, request=self.request)


class AdminFAQViewSet(AdminContentMixin, viewsets.ModelViewSet):
    serializer_class = FAQEntrySerializer
    queryset = FAQEntry.objects.all()
    content_type = "faq"
    required_permission_by_action = {
        "list": "sitecontent.view_faqentry",
        "retrieve": "sitecontent.view_faqentry",
        "create": "sitecontent.add_faqentry",
        "update": "sitecontent.change_faqentry",
        "partial_update": "sitecontent.change_faqentry",
        "destroy": "sitecontent.delete_faqentry",
    }


class AdminNewsViewSet(AdminContentMixin, viewsets.ModelViewSet):
    serializer_class = NewsArticleSerializer
    queryset = NewsArticle.objects.all()
    content_type = "news"
    required_permission_by_action = {
        "list": "sitecontent.view_newsarticle",
        "retrieve": "sitecontent.view_newsarticle",
        "create": "sitecontent.add_newsarticle",
        "update": "sitecontent.change_newsarticle",
        "partial_update": "sitecontent.change_newsarticle",
        "destroy": "sitecontent.delete_newsarticle",
    }

class AdminPageViewSet(AdminContentMixin, viewsets.ModelViewSet):
    serializer_class = PageContentSerializer
    queryset = PageContent.objects.all()
    content_type = "page"
    http_method_names = ("get", "post", "patch", "head", "options")
    required_permission_by_action = {
        "list": "sitecontent.view_pagecontent",
        "retrieve": "sitecontent.view_pagecontent",
        "create": "sitecontent.add_pagecontent",
        "update": "sitecontent.change_pagecontent",
        "partial_update": "sitecontent.change_pagecontent",
        "destroy": "sitecontent.delete_pagecontent",
    }


class AdminImageViewSet(AdminContentMixin, viewsets.ModelViewSet):
    serializer_class = SiteImageSerializer
    queryset = SiteImage.objects.all()
    content_type = "image"
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    required_permission_by_action = {
        "list": "sitecontent.view_siteimage",
        "retrieve": "sitecontent.view_siteimage",
        "create": "sitecontent.add_siteimage",
        "update": "sitecontent.change_siteimage",
        "partial_update": "sitecontent.change_siteimage",
        "destroy": "sitecontent.delete_siteimage",
    }

    def perform_create(self, serializer):
        slot = serializer.validated_data["slot"]
        is_replacement = SiteImage.objects.filter(slot=slot).exists()
        obj = serializer.save()
        action = "updated" if is_replacement else "created"
        record_event(actor=self.request.user, action=f"site_content.image.{action}", target=obj, request=self.request)


class AdminSiteConfigurationView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission_by_method = {
        "get": "sitecontent.view_siteconfiguration",
        "patch": "sitecontent.change_siteconfiguration",
    }

    @extend_schema(responses=SiteConfigurationResponseSerializer, summary="Lire la configuration du site", tags=["Contenu du site"])
    def get(self, request):
        config = SiteConfiguration.objects.filter(pk=1).first()
        return Response({**SiteConfigurationSerializer(config).data, "use_database_config": True} if config else {"whatsapp_number": "", "updated_at": None, "use_database_config": False})

    @extend_schema(
        request=SiteConfigurationSerializer,
        responses=SiteConfigurationResponseSerializer,
        summary="Modifier la configuration du site",
        tags=["Contenu du site"],
    )
    def patch(self, request):
        config, _ = SiteConfiguration.objects.get_or_create(pk=1)
        serializer = SiteConfigurationSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save(updated_by=request.user)
        record_event(actor=request.user, action="site_content.configuration.updated", target=config, request=request)
        return Response(SiteConfigurationSerializer(config).data)


class PublicSiteConfigurationView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=SiteConfigurationResponseSerializer, summary="Lire la configuration publique du site", tags=["Contenu du site"])
    def get(self, request):
        config = SiteConfiguration.objects.filter(pk=1).first()
        return Response({"whatsapp_number": config.whatsapp_number if config else "", "use_database_config": config is not None})


class PublicFAQView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=PublicFAQResponseSerializer, summary="Lister les questions fréquentes publiques", tags=["Contenu du site"])
    def get(self, request):
        return Response({"managed": FAQEntry.objects.exists(), "entries": FAQEntrySerializer(FAQEntry.objects.filter(is_visible=True), many=True).data})


class PublicNewsView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=NewsArticleSerializer(many=True), summary="Lister les actualités publiées", tags=["Contenu du site"])
    def get(self, request):
        return Response(NewsArticleSerializer(NewsArticle.objects.filter(is_published=True), many=True).data)


class PublicPageView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=PageContentSerializer, summary="Lire une page éditoriale publique", tags=["Contenu du site"])
    def get(self, request, page):
        content = PageContent.objects.filter(page=page).first()
        if not content:
            raise Http404
        return Response(PageContentSerializer(content).data)


class PublicSiteImageListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses=PublicSiteImageListResponseSerializer,
        summary="Lister les images publiques du site",
        operation_id="site_content_public_images_list",
        tags=["Contenu du site"],
    )
    def get(self, request):
        return Response({
            "images": SiteImageSerializer(SiteImage.objects.filter(is_visible=True), many=True, context={"request": request}).data,
            "hidden_slots": list(SiteImage.objects.filter(is_visible=False).values_list("slot", flat=True)),
        })


class PublicSiteImageView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        responses=image_schema_response(),
        summary="Télécharger une image publique du site",
        operation_id="site_content_public_image_by_slot_retrieve",
        tags=["Contenu du site"],
    )
    def get(self, request, slot):
        image = SiteImage.objects.filter(slot=slot, is_visible=True).first()
        if not image:
            raise Http404
        try:
            stream = image.image.open("rb")
        except (OSError, ValueError) as exc:
            raise Http404 from exc
        content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(Path(image.image.name).suffix.lower(), "application/octet-stream")
        response = FileResponse(stream, content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "public, max-age=300"
        return response
