from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    renderer_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .api import (
    CollaboratorListView,
    SiteSettingsView,
    TestimonialListView,
    api_router,
)


@api_view(["GET", "HEAD"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
def cms_api_root(request):
    return Response(
        {
            "pages": "/api/cms/v2/pages/",
            "collaborators": "/api/cms/v2/collaborators/",
            "testimonials": "/api/cms/v2/testimonials/",
            "settings": "/api/cms/v2/settings/",
        }
    )


urlpatterns = [
    path("", cms_api_root, name="cms-api-root"),
    path("collaborators/", CollaboratorListView.as_view(), name="cms-collaborators"),
    path("testimonials/", TestimonialListView.as_view(), name="cms-testimonials"),
    path("settings/", SiteSettingsView.as_view(), name="cms-settings"),
    path("", api_router.urls),
]
