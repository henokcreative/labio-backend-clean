"""
URL configuration for labio project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter

from wagtail.admin import urls as wagtailadmin_urls

from .serializers import (
    CustomTokenObtainPairSerializer,
    PasswordBoundTokenRefreshSerializer,
)
from .login_throttle import LoginAttemptGuard
from clients.portal_views import DashboardViewSet, PortalMessageViewSet, ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("messages", PortalMessageViewSet, basename="portal-message")
router.register("auth/dashboard", DashboardViewSet, basename="dashboard")

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    throttle_response = {
        "detail": "Unable to process your login request right now."
    }

    def post(self, request, *args, **kwargs):
        guard = LoginAttemptGuard(request)
        if not guard.allow_attempt():
            response = Response(self.throttle_response, status=429)
            response["Retry-After"] = str(guard.retry_after)
            return response

        response = super().post(request, *args, **kwargs)
        guard.clear_identifier_failures()
        return response


class PasswordBoundTokenRefreshView(TokenRefreshView):
    serializer_class = PasswordBoundTokenRefreshSerializer

@api_view(['GET'])
def api_root(request):
    """API root endpoint - lists all available endpoints"""
    return Response({
        'message': 'Welcome to LaBioMedia API',
        'version': '1.0',
        'endpoints': {
            'admin': '/admin/',
            'contacts': '/api/contacts/',
            'messaging': '/api/messaging/',
            'portal': {
                'dashboard': '/api/auth/dashboard/',
                'projects': '/api/projects/',
                'messages': '/api/messages/',
            },
            'auth': {
                'login': '/api/auth/login/',
                'refresh': '/api/auth/refresh/',
            }
        }
    })


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [

    path("", api_root),

    path("admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("api/cms/v2/", include("public_content.urls")),
    path("api/contacts/", include("contacts.urls")),
    path("api/messaging/", include("messaging.urls")),


    path(
        "api/auth/login/",
        CustomTokenObtainPairView.as_view(),
        name="token_obtain_pair"
    ),

    path(
        "api/auth/refresh/",
        PasswordBoundTokenRefreshView.as_view(),
        name="token_refresh"
    ),


    path(
        "api/auth/",
        include("clients.urls")
    ),
    path("api/", include(router.urls)),
    path("health/", health_check),

]
