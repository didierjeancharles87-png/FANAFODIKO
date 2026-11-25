from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from apps.core.throttling import (
    CsrfIPRateThrottle,
    LoginAccountRateThrottle,
    LoginIPRateThrottle,
    RegistrationAccountRateThrottle,
    RegistrationIPRateThrottle,
)
from apps.professionals.serializers import ProfessionalProfileSerializer
from .auth_serializers import AuthSessionSerializer, CsrfCookieSerializer, ProfessionalLoginSerializer, ProfessionalRegistrationSerializer
from .permissions import IsActiveAccount, IsLogoutSessionAllowed
from .models import AccountProfile


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfCookieView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = (CsrfIPRateThrottle,)

    @extend_schema(responses=CsrfCookieSerializer, summary="Initialiser le cookie CSRF", tags=["Authentification"])
    def get(self, request):
        return Response({"csrf": "cookie-set"})


class ProfessionalRegistrationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = (RegistrationIPRateThrottle, RegistrationAccountRateThrottle)

    @extend_schema(request=ProfessionalRegistrationSerializer, responses={201: ProfessionalProfileSerializer}, summary="Créer un compte professionnel", tags=["Authentification"])
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = ProfessionalRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user, profile = serializer.save()
                login(request._request, user)
        except IntegrityError as exc:
            raise ValidationError({"email": ["Un compte existe déjà avec ces informations."]}) from exc
        return Response(ProfessionalProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class ProfessionalLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = (LoginIPRateThrottle, LoginAccountRateThrottle)

    @extend_schema(request=ProfessionalLoginSerializer, responses={200: AuthSessionSerializer}, summary="Ouvrir une session professionnelle", tags=["Authentification"])
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = ProfessionalLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_record = user_model.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        user = authenticate(request._request, username=user_record.get_username(), password=serializer.validated_data["password"]) if user_record else None
        if user is None or not user.is_active:
            raise AuthenticationFailed("Adresse e-mail ou mot de passe incorrect.")
        try:
            if user.account_profile.status != "active":
                raise AuthenticationFailed("Ce compte est suspendu ou clôturé.")
        except AccountProfile.DoesNotExist as exc:
            raise AuthenticationFailed("Ce compte n’est pas configuré.") from exc
        login(request._request, user)
        return Response(AuthSessionSerializer(user).data)


class ProfessionalLogoutView(APIView):
    permission_classes = [IsLogoutSessionAllowed]

    @extend_schema(request=None, responses={204: None}, summary="Fermer la session professionnelle", tags=["Authentification"])
    def post(self, request):
        # Une session révoquée est anonyme : DRF n'applique pas automatiquement
        # la vérification CSRF dans ce cas. On l'impose explicitement ici.
        SessionAuthentication().enforce_csrf(request)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(responses=AuthSessionSerializer, summary="Consulter la session actuelle", tags=["Authentification"])
    def get(self, request):
        return Response(AuthSessionSerializer(request.user).data)
