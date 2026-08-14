from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.models import Site

from .api_fields import get_rendition_data, only_public_pages, public_page_summary
from .models import (
    AboutPage,
    CaseStudyPage,
    Collaborator,
    HomePage,
    PortfolioIndexPage,
    PricingPage,
    ServiceIndexPage,
    ServicePage,
    SiteSettings,
    StandardPage,
    Testimonial,
)


PUBLIC_PAGE_MODELS = (
    HomePage,
    ServiceIndexPage,
    ServicePage,
    PortfolioIndexPage,
    CaseStudyPage,
    PricingPage,
    AboutPage,
    StandardPage,
)


class PublicContentPagesAPIViewSet(PagesAPIViewSet):
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]
    body_fields = ["id", "title"]
    meta_fields = [
        "type",
        "detail_url",
        "slug",
        "seo_title",
        "search_description",
        "first_published_at",
        "locale",
    ]
    listing_default_fields = [
        "id",
        "type",
        "detail_url",
        "title",
        "slug",
        "first_published_at",
    ]
    nested_default_fields = ["id", "type", "detail_url", "title", "slug"]
    detail_only_fields = []

    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .live()
            .public()
            .type(*PUBLIC_PAGE_MODELS)
        )


class PublicAPIBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]
    http_method_names = ["get", "head", "options"]


class CollaboratorSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Collaborator
        fields = [
            "id",
            "organization_name",
            "logo",
            "url",
            "display_order",
            "visual_variant",
        ]

    def get_logo(self, obj):
        return get_rendition_data(obj.logo, "max-600x300", obj.logo_alt)


class TestimonialSerializer(serializers.ModelSerializer):
    related_service = serializers.SerializerMethodField()
    related_case_study = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            "id",
            "quote",
            "person",
            "role",
            "organization",
            "related_service",
            "related_case_study",
        ]

    @staticmethod
    def public_relation(page):
        if page is None or not only_public_pages([page]):
            return None
        return public_page_summary(page)

    def get_related_service(self, obj):
        return self.public_relation(obj.related_service)

    def get_related_case_study(self, obj):
        return self.public_relation(obj.related_case_study)


class CollaboratorListView(PublicAPIBaseView):
    def get(self, request):
        collaborators = Collaborator.objects.filter(live=True, active=True)
        return Response(CollaboratorSerializer(collaborators, many=True).data)


class TestimonialListView(PublicAPIBaseView):
    def get(self, request):
        testimonials = Testimonial.objects.filter(live=True, active=True).select_related(
            "related_service",
            "related_case_study",
        )
        return Response(TestimonialSerializer(testimonials, many=True).data)


class SiteSettingsView(PublicAPIBaseView):
    def get(self, request):
        site = Site.find_for_request(request)
        if site is None:
            site = Site.objects.filter(is_default_site=True).first()
        settings = (
            SiteSettings.objects.filter(site=site).first()
            if site is not None
            else None
        )
        if settings is None:
            return Response(
                {
                    "public_contact_email": "",
                    "public_phone": "",
                    "address": "",
                    "default_cta_label": "",
                    "default_cta_url": "",
                    "social_links": [],
                    "default_social_image": None,
                }
            )
        social_links = settings.social_links.stream_block.get_api_representation(
            settings.social_links,
            context={"request": request},
        )
        return Response(
            {
                "public_contact_email": settings.public_contact_email,
                "public_phone": settings.public_phone,
                "address": settings.address,
                "default_cta_label": settings.default_cta_label,
                "default_cta_url": settings.default_cta_url,
                "social_links": social_links,
                "default_social_image": get_rendition_data(
                    settings.default_social_image,
                    "fill-1200x630",
                ),
            }
        )


api_router = WagtailAPIRouter("public_content_api")
api_router.register_endpoint("pages", PublicContentPagesAPIViewSet)
