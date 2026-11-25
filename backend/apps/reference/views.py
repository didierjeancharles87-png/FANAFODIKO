from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import extend_schema

from .models import Country
from .serializers import CountrySerializer


class CountryListView(ListAPIView):
    serializer_class = CountrySerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        return Country.objects.filter(is_active=True)

    @extend_schema(summary="Lister les pays actifs", tags=["Référentiels"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
