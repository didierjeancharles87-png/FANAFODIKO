from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    version = serializers.CharField()

class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(responses=HealthSerializer, summary="Vérifier la disponibilité de l’API", tags=["Système"])
    def get(self, request):
        version = settings.SPECTACULAR_SETTINGS.get("VERSION", "0.3.0")
        return Response({"status": "ok", "service": "fanafodiko-api", "version": version})
