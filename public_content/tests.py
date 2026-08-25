import base64
from datetime import time, timedelta
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.models import Page, PageViewRestriction, Site

from clients.permissions import PORTAL_STAFF_PERMISSION
from .blocks import CaseStudyShowcaseBlock, UpdateShowcaseBlock
from .models import (
    AboutPage,
    AboutPageTestimonial,
    ArticlePage,
    CaseStudyPage,
    Collaborator,
    ContactPage,
    EventPage,
    HomePage,
    HomePageCollaborator,
    HomePageFeaturedCaseStudy,
    HomePageFeaturedService,
    HomePageTestimonial,
    PortfolioIndexPage,
    PricingItem,
    PricingPage,
    ServiceIndexPage,
    ServicePage,
    ServicePageRelatedCaseStudy,
    ServicePageTestimonial,
    SiteSettings,
    StandardPage,
    Testimonial,
    UpdatesIndexPage,
)


TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

ONE_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)


@override_settings(STORAGES=TEST_STORAGES)
class PublicContentSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.site = Site.objects.get(is_default_site=True)
        cls.site.root_page = root
        cls.site.save(update_fields=["root_page"])
        for existing_page in root.get_children():
            existing_page.delete()

        cls.image = get_image_model().objects.create(
            title="Editorial image",
            file=SimpleUploadedFile(
                "editorial.gif",
                ONE_PIXEL_GIF,
                content_type="image/gif",
            ),
        )
        cls.home = HomePage(
            title="LaBio Media",
            slug="home",
            hero_eyebrow="Creative production",
            hero_heading="Stories with impact",
            hero_copy="Public editorial copy.",
            hero_image=cls.image,
            hero_image_alt="A LaBio Media production",
            primary_cta_label="View work",
            primary_cta_url="https://example.com/work",
            secondary_cta_label="Contact",
            secondary_cta_url="https://example.com/contact",
            about_heading="About LaBio",
            about_copy="A public about teaser.",
            about_image=cls.image,
            about_image_alt="LaBio collaborators at work",
            contact_heading="Start a project",
            contact_copy="Public contact copy.",
            contact_cta_label="Get in touch",
            contact_cta_url="https://example.com/contact",
        )
        root.add_child(instance=cls.home)
        cls.home.save_revision().publish()

        cls.site.hostname = "testserver"
        cls.site.port = 80
        cls.site.root_page = cls.home
        cls.service_index = ServiceIndexPage(
            title="Services",
            slug="services",
        )
        cls.home.add_child(instance=cls.service_index)
        cls.service_index.save_revision().publish()

        cls.service = ServicePage(
            title="Film production",
            slug="film-production",
            summary="Public service summary.",
            cta_label="Start a film project",
            cta_url="https://example.com/contact",
        )
        cls.service_index.add_child(instance=cls.service)
        cls.service.save_revision().publish()

        cls.portfolio_index = PortfolioIndexPage(
            title="Work",
            slug="work",
        )
        cls.home.add_child(instance=cls.portfolio_index)
        cls.portfolio_index.save_revision().publish()

        cls.case_study = CaseStudyPage(
            title="Public case study",
            slug="public-case-study",
            client_display_name="Editorial Client Name",
            category="Film",
            summary="Public case study summary.",
            project_year="2025",
            challenge="Explain a complex research programme clearly.",
            approach="Build the story around the researchers and their work.",
            deliverables=[
                ("deliverable", "Editorial film"),
                ("deliverable", "Social cutdowns"),
            ],
            outcome="A focused story ready for public release.",
            project_url="https://project.example.com",
            cta_label="Discuss a similar project",
            cta_url="https://labiomedia.com/contact",
            hero_image=cls.image,
            hero_image_alt="A finished public production",
            embed_url="https://example.com/public-video",
            featured=True,
        )
        cls.portfolio_index.add_child(instance=cls.case_study)
        cls.case_study.services.add(cls.service)
        cls.case_study.save_revision().publish()
        ServicePageRelatedCaseStudy.objects.create(
            page=cls.service,
            case_study=cls.case_study,
            sort_order=0,
        )

        cls.about = AboutPage(
            title="About",
            slug="about",
            hero_image=cls.image,
            hero_image_alt="The LaBio Media team",
            intro="Public about introduction.",
        )
        cls.home.add_child(instance=cls.about)
        cls.about.save_revision().publish()

        cls.contact = ContactPage(
            title="Contact",
            slug="contact",
            eyebrow="Start a conversation",
            intro="Tell us about the research communication you need.",
            body=[
                ("heading", {"text": "A thoughtful first conversation", "level": "h2"}),
                ("rich_text", "<p>Share a little context and we will respond.</p>"),
            ],
        )
        cls.home.add_child(instance=cls.contact)
        cls.contact.save_revision().publish()

        cls.pricing = PricingPage(
            title="Pricing",
            slug="pricing",
            intro="Flexible starting points for public projects.",
            positioning_message=(
                "Every project is scoped individually based on goals, "
                "timeline, and complexity."
            ),
        )
        cls.home.add_child(instance=cls.pricing)
        cls.pricing.save_revision().publish()
        cls.pricing_first = PricingItem.objects.create(
            page=cls.pricing,
            title="Photography",
            price_label="From €400",
            description="Purposeful photography for research.",
            ideal_for="Research teams building a reusable image library.",
            features=[("feature", "Planning"), ("feature", "Edited delivery")],
            context="Travel and specialist production costs are scoped separately.",
            cta_label="Request a quote",
            cta_url="https://example.com/contact",
            featured=True,
            active=True,
            related_services=[("service", cls.service)],
            related_case_studies=[("case_study", cls.case_study)],
            sort_order=0,
        )
        PricingItem.objects.create(
            page=cls.pricing,
            title="Hidden service",
            pricing_mode=PricingItem.PricingMode.CUSTOM,
            currency="",
            price_label="Contact us",
            description="Not currently offered.",
            cta_label="Contact",
            cta_url="https://example.com/contact",
            active=False,
            sort_order=1,
        )
        cls.pricing_second = PricingItem.objects.create(
            page=cls.pricing,
            title="Video production",
            pricing_mode=PricingItem.PricingMode.FIXED,
            currency="€",
            price_label="800",
            description="Editorial video production.",
            cta_label="Request a quote",
            cta_url="https://example.com/contact",
            active=True,
            sort_order=2,
        )

        HomePageFeaturedService.objects.create(
            page=cls.home,
            service=cls.service,
            sort_order=0,
        )
        HomePageFeaturedCaseStudy.objects.create(
            page=cls.home,
            case_study=cls.case_study,
            sort_order=0,
        )
        cls.site.save()

        cls.published_page = StandardPage(
            title="Published page",
            slug="published-page",
            body=[
                (
                    "rich_text",
                    "<p>Safe public content with <strong>controlled markup</strong>.</p>",
                )
            ],
        )
        cls.home.add_child(instance=cls.published_page)
        cls.published_page.save_revision().publish()

        cls.draft_page = StandardPage(
            title="Draft page",
            slug="draft-page",
            live=False,
            body=[("rich_text", "<p>Unpublished private draft.</p>")],
        )
        cls.home.add_child(instance=cls.draft_page)
        cls.draft_page.save_revision()

        cls.published_collaborator = Collaborator.objects.create(
            organization_name="Published Partner",
            logo=cls.image,
            logo_alt="Published Partner logo",
            url="https://partner.example.com",
            display_order=1,
            active=True,
            live=True,
        )
        cls.second_published_collaborator = Collaborator.objects.create(
            organization_name="Second Published Partner",
            logo=cls.image,
            logo_alt="Second Published Partner logo",
            url="https://second-partner.example.com",
            display_order=0,
            active=True,
            live=True,
        )
        cls.inactive_collaborator = Collaborator.objects.create(
            organization_name="Inactive Partner",
            logo=cls.image,
            logo_alt="Inactive Partner logo",
            url="https://inactive.example.com",
            display_order=2,
            active=False,
            live=True,
        )
        cls.draft_collaborator = Collaborator.objects.create(
            organization_name="Draft Partner",
            logo=cls.image,
            logo_alt="Draft Partner logo",
            url="https://draft.example.com",
            display_order=3,
            active=True,
            live=False,
        )
        for sort_order, collaborator in enumerate(
            (
                cls.draft_collaborator,
                cls.published_collaborator,
                cls.inactive_collaborator,
                cls.second_published_collaborator,
            )
        ):
            HomePageCollaborator.objects.create(
                page=cls.home,
                collaborator=collaborator,
                sort_order=sort_order,
            )
        cls.home.save_revision().publish()

        cls.published_testimonial = Testimonial.objects.create(
            quote="A published testimonial.",
            person="Published Person",
            portrait=cls.image,
            role="Producer",
            organization="Published Organization",
            active=True,
            live=True,
        )
        cls.inactive_testimonial = Testimonial.objects.create(
            quote="An inactive testimonial.",
            person="Inactive Person",
            active=False,
            live=True,
        )
        cls.draft_testimonial = Testimonial.objects.create(
            quote="A draft testimonial.",
            person="Draft Person",
            active=True,
            live=False,
        )
        cls.second_published_testimonial = Testimonial.objects.create(
            quote="A second published testimonial.",
            person="Second Published Person",
            role="Researcher",
            organization="Second Published Organization",
            related_service=cls.service,
            active=True,
            live=True,
        )
        for sort_order, testimonial in enumerate(
            (
                cls.second_published_testimonial,
                cls.draft_testimonial,
                cls.inactive_testimonial,
                cls.published_testimonial,
            )
        ):
            ServicePageTestimonial.objects.create(
                page=cls.service,
                testimonial=testimonial,
                sort_order=sort_order,
            )
        for sort_order, testimonial in enumerate(
            (
                cls.draft_testimonial,
                cls.published_testimonial,
                cls.inactive_testimonial,
                cls.second_published_testimonial,
            )
        ):
            HomePageTestimonial.objects.create(
                page=cls.home,
                testimonial=testimonial,
                sort_order=sort_order,
            )
        for sort_order, testimonial in enumerate(
            (
                cls.draft_testimonial,
                cls.second_published_testimonial,
                cls.inactive_testimonial,
                cls.published_testimonial,
            )
        ):
            AboutPageTestimonial.objects.create(
                page=cls.about,
                testimonial=testimonial,
                sort_order=sort_order,
            )
        cls.home.save_revision().publish()

        SiteSettings.objects.create(
            site=cls.site,
            legal_business_name="LaBio Media Oy",
            business_id="1234567-8",
            city="Turku",
            country="Finland",
            public_contact_email="hello@example.com",
            public_phone="+358 00 000 0000",
            address="Helsinki, Finland",
            default_cta_label="Contact us",
            default_cta_url="https://example.com/contact",
            social_links=[
                (
                    "social_link",
                    {
                        "label": "Instagram",
                        "url": "https://instagram.com/example",
                    },
                )
            ],
            navigation_links=[
                (
                    "navigation_link",
                    {
                        "label": "About",
                        "page": cls.about,
                        "enabled": True,
                        "external": False,
                    },
                ),
                (
                    "navigation_link",
                    {
                        "label": "External",
                        "url": "https://example.org/updates",
                        "enabled": True,
                        "external": True,
                    },
                ),
                (
                    "navigation_link",
                    {
                        "label": "Disabled",
                        "url": "https://example.org/disabled",
                        "enabled": False,
                    },
                ),
                (
                    "navigation_link",
                    {
                        "label": "Draft",
                        "page": cls.draft_page,
                        "enabled": True,
                    },
                ),
            ],
            default_social_image=cls.image,
        )

        cls.wagtail_access_permission = Permission.objects.get(
            content_type__app_label="wagtailadmin",
            codename="access_admin",
        )
        cls.portal_permission = Permission.objects.get(
            content_type__app_label="clients",
            codename=PORTAL_STAFF_PERMISSION.split(".", 1)[1],
        )

    def setUp(self):
        self.api = APIClient()

    @staticmethod
    def _collect_keys(value):
        keys = set()
        if isinstance(value, dict):
            keys.update(value)
            for nested in value.values():
                keys.update(PublicContentSecurityTests._collect_keys(nested))
        elif isinstance(value, list):
            for nested in value:
                keys.update(PublicContentSecurityTests._collect_keys(nested))
        return keys

    def _cms_editor(self):
        group = Group.objects.create(name="CMS Editors test group")
        group.permissions.add(self.wagtail_access_permission)
        editor = User.objects.create_user(
            username="cms-editor",
            email="cms-editor@example.com",
            password="Password!123",
            is_active=True,
            is_staff=True,
        )
        editor.groups.add(group)
        return editor, group

    def test_cms_editor_can_enter_wagtail_without_portal_access(self):
        editor, _ = self._cms_editor()
        self.client.force_login(editor)

        response = self.client.get("/cms/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(editor.has_perm(PORTAL_STAFF_PERMISSION))

        self.api.force_authenticate(editor)
        self.assertEqual(self.api.get("/api/projects/").status_code, 403)
        self.assertEqual(self.api.get("/api/messages/").status_code, 403)
        self.assertEqual(self.api.get("/api/auth/dashboard/").status_code, 403)

    def test_cms_group_does_not_receive_portal_permission(self):
        editor, group = self._cms_editor()

        self.assertNotIn(self.portal_permission, group.permissions.all())
        self.assertFalse(editor.has_perm(PORTAL_STAFF_PERMISSION))

    def test_portal_staff_permission_remains_independent(self):
        portal_staff = User.objects.create_user(
            username="portal-staff",
            email="portal-staff@example.com",
            password="Password!123",
            is_active=True,
            is_staff=False,
        )
        portal_staff.user_permissions.add(self.portal_permission)
        self.api.force_authenticate(portal_staff)

        self.assertEqual(self.api.get("/api/projects/").status_code, 200)
        self.assertFalse(
            portal_staff.has_perm("wagtailadmin.access_admin")
        )

    def test_only_published_pages_appear_in_public_api(self):
        response = self.client.get("/api/cms/v2/pages/")

        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.json()["items"]}
        self.assertIn(self.published_page.title, titles)
        self.assertNotIn(self.draft_page.title, titles)

    def test_draft_page_detail_is_not_public(self):
        self.assertEqual(
            self.client.get(
                f"/api/cms/v2/pages/{self.draft_page.pk}/"
            ).status_code,
            404,
        )

    def test_collaborator_endpoint_exposes_only_active_published_items(self):
        response = self.client.get("/api/cms/v2/collaborators/")

        self.assertEqual(response.status_code, 200)
        names = {
            item["organization_name"]
            for item in response.json()
        }
        self.assertEqual(
            names,
            {"Published Partner", "Second Published Partner"},
        )
        collaborator = response.json()[0]
        self.assertEqual(
            set(collaborator),
            {
                "id",
                "organization_name",
                "logo",
                "url",
                "display_order",
                "visual_variant",
            },
        )
        self.assertEqual(
            set(collaborator["logo"]),
            {"url", "width", "height", "alt"},
        )

    def test_testimonial_endpoint_exposes_only_active_published_items(self):
        response = self.client.get("/api/cms/v2/testimonials/")

        self.assertEqual(response.status_code, 200)
        people = {item["person"] for item in response.json()}
        self.assertEqual(
            people,
            {"Published Person", "Second Published Person"},
        )
        published = next(
            item
            for item in response.json()
            if item["person"] == "Published Person"
        )
        self.assertEqual(
            set(published["portrait"]),
            {"url", "width", "height", "alt"},
        )
        self.assertLessEqual(published["portrait"]["width"], 144)
        self.assertLessEqual(published["portrait"]["height"], 144)
        self.assertEqual(
            published["portrait"]["width"],
            published["portrait"]["height"],
        )
        self.assertEqual(
            published["portrait"]["alt"],
            "Portrait of Published Person",
        )
        second = next(
            item
            for item in response.json()
            if item["person"] == "Second Published Person"
        )
        self.assertIsNone(second["portrait"])

    def test_settings_endpoint_exposes_only_public_fields(self):
        response = self.client.get("/api/cms/v2/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {
                "legal_business_name",
                "business_id",
                "city",
                "country",
                "public_contact_email",
                "public_phone",
                "address",
                "default_cta_label",
                "default_cta_url",
                "social_links",
                "navigation_links",
                "default_social_image",
            },
        )
        self.assertEqual(
            set(response.json()["default_social_image"]),
            {"url", "width", "height", "alt"},
        )
        self.assertEqual(response.json()["legal_business_name"], "LaBio Media Oy")
        self.assertEqual(response.json()["business_id"], "1234567-8")
        self.assertEqual(response.json()["city"], "Turku")
        self.assertEqual(response.json()["country"], "Finland")
        self.assertEqual(
            response.json()["navigation_links"],
            [
                {
                    "label": "About",
                    "url": "",
                    "page": {
                        "id": self.about.pk,
                        "title": "About",
                        "slug": "about",
                        "type": "public_content.AboutPage",
                    },
                    "external": False,
                },
                {
                    "label": "External",
                    "url": "https://example.org/updates",
                    "page": None,
                    "external": True,
                },
            ],
        )

    def test_settings_endpoint_uses_empty_public_identity_without_settings(self):
        SiteSettings.objects.all().delete()

        response = self.client.get("/api/cms/v2/settings/")

        self.assertEqual(response.status_code, 200)
        for field_name in (
            "legal_business_name",
            "business_id",
            "city",
            "country",
            "public_contact_email",
            "public_phone",
            "address",
        ):
            self.assertEqual(response.json()[field_name], "")
        self.assertEqual(response.json()["navigation_links"], [])

    def test_cms_api_is_json_read_only_and_requires_no_jwt(self):
        for url in (
            "/api/cms/v2/",
            "/api/cms/v2/pages/",
            "/api/cms/v2/collaborators/",
            "/api/cms/v2/testimonials/",
            "/api/cms/v2/settings/",
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(self.client.head(url).status_code, 200, url)
            self.assertEqual(self.client.options(url).status_code, 200, url)
            self.assertEqual(self.client.post(url, {}).status_code, 405, url)

    def test_page_detail_uses_controlled_fields_and_image_renditions(self):
        response = self.client.get(
            f"/api/cms/v2/pages/{self.home.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data["hero_image"]),
            {"url", "width", "height", "alt"},
        )
        self.assertEqual(
            data["hero_image"]["alt"],
            "A LaBio Media production",
        )
        self.assertNotIn("file", data["hero_image"])
        self.assertNotIn("original", data["hero_image"])

    def test_all_public_page_types_have_safe_public_api_details(self):
        pages = (
            self.home,
            self.service_index,
            self.service,
            self.portfolio_index,
            self.case_study,
            self.about,
            self.contact,
            self.pricing,
            self.published_page,
        )
        responses = {}
        for page in pages:
            response = self.client.get(
                f"/api/cms/v2/pages/{page.pk}/"
            )
            self.assertEqual(response.status_code, 200, page.title)
            responses[page.pk] = response.json()

        home_data = responses[self.home.pk]
        self.assertEqual(
            [item["id"] for item in home_data["featured_services"]],
            [self.service.pk],
        )
        self.assertEqual(
            [item["id"] for item in home_data["selected_work"]],
            [self.case_study.pk],
        )
        self.assertTrue(home_data["selected_work_enabled"])
        self.assertEqual(home_data["selected_work_eyebrow"], "Selected work")
        self.assertEqual(
            home_data["selected_work_heading"],
            "Turning research into meaningful stories",
        )
        self.assertEqual(home_data["selected_work_cta_label"], "View all work")
        self.assertEqual(
            home_data["selected_work_cta_url"],
            "https://labiomedia.com/work",
        )
        self.assertTrue(home_data["services_enabled"])
        self.assertEqual(home_data["services_eyebrow"], "What we do")
        self.assertEqual(
            home_data["services_heading"],
            "Communication solutions for research and innovation.",
        )
        self.assertEqual(home_data["services_cta_label"], "See all services")
        self.assertEqual(
            home_data["services_cta_url"],
            "https://labiomedia.com/services",
        )
        self.assertTrue(home_data["collaborators_enabled"])
        self.assertEqual(
            home_data["collaborators_heading"],
            "Trusted by research groups and organisations",
        )
        self.assertEqual(
            [item["id"] for item in home_data["collaborators"]],
            [
                self.published_collaborator.pk,
                self.second_published_collaborator.pk,
            ],
        )
        self.assertEqual(
            set(home_data["collaborators"][0]),
            {
                "id",
                "organization_name",
                "logo",
                "url",
                "display_order",
                "visual_variant",
            },
        )
        self.assertTrue(home_data["testimonials_enabled"])
        self.assertEqual(home_data["testimonials_heading"], "Client perspectives")
        self.assertEqual(
            [item["id"] for item in home_data["testimonials"]],
            [
                self.published_testimonial.pk,
                self.second_published_testimonial.pk,
            ],
        )
        self.assertEqual(
            set(home_data["testimonials"][0]),
            {
                "id",
                "quote",
                "person",
                "portrait",
                "role",
                "organization",
                "related_service",
                "related_case_study",
            },
        )
        self.assertEqual(
            home_data["testimonials"][0]["portrait"]["alt"],
            "Portrait of Published Person",
        )
        self.assertTrue(home_data["about_enabled"])
        self.assertEqual(home_data["about_eyebrow"], "About LaBio Media")
        self.assertEqual(home_data["about_cta_label"], "More about LaBio Media")
        self.assertEqual(
            home_data["about_cta_url"],
            "https://labiomedia.com/about",
        )
        self.assertTrue(home_data["updates_enabled"])
        self.assertEqual(home_data["updates_eyebrow"], "From LaBio")
        self.assertEqual(
            home_data["updates_heading"],
            "A few notes, ideas and milestones.",
        )
        self.assertEqual(home_data["updates_item_count"], 3)
        self.assertEqual(home_data["updates_cta_label"], "View all updates")
        self.assertEqual(
            home_data["updates_cta_url"],
            "https://labiomedia.com/updates",
        )
        self.assertEqual(home_data["latest_updates"], [])
        self.assertTrue(home_data["contact_enabled"])
        self.assertEqual(home_data["contact_eyebrow"], "Contact")
        service_data = responses[self.service.pk]
        self.assertNotIn("hero_image", service_data)
        self.assertTrue(service_data["testimonials_enabled"])
        self.assertEqual(
            service_data["testimonials_heading"],
            "Client perspectives",
        )
        self.assertEqual(
            [item["id"] for item in service_data["testimonials"]],
            [
                self.second_published_testimonial.pk,
                self.published_testimonial.pk,
            ],
        )
        self.assertTrue(service_data["related_work_enabled"])
        self.assertEqual(service_data["related_work_heading"], "Related work")
        self.assertEqual(service_data["cta_heading"], "Have a project in mind?")
        self.assertEqual(
            [
                item["id"]
                for item in service_data["related_case_studies"]
            ],
            [self.case_study.pk],
        )
        self.assertEqual(
            set(service_data["related_case_studies"][0]["hero_image"]),
            {"url", "width", "height", "alt"},
        )
        self.assertEqual(
            [item["id"] for item in responses[self.case_study.pk]["services"]],
            [self.service.pk],
        )
        case_study_data = responses[self.case_study.pk]
        self.assertEqual(case_study_data["client_display_name"], "Editorial Client Name")
        self.assertEqual(case_study_data["project_year"], "2025")
        self.assertEqual(
            case_study_data["challenge"],
            "Explain a complex research programme clearly.",
        )
        self.assertEqual(
            case_study_data["approach"],
            "Build the story around the researchers and their work.",
        )
        self.assertEqual(
            [item["value"] for item in case_study_data["deliverables"]],
            ["Editorial film", "Social cutdowns"],
        )
        self.assertEqual(
            case_study_data["outcome"],
            "A focused story ready for public release.",
        )
        self.assertEqual(
            case_study_data["project_url"],
            "https://project.example.com",
        )
        self.assertEqual(case_study_data["cta_label"], "Discuss a similar project")
        self.assertEqual(
            case_study_data["cta_url"],
            "https://labiomedia.com/contact",
        )

        about_data = responses[self.about.pk]
        self.assertEqual(about_data["page_eyebrow"], "About LaBio Media")
        self.assertEqual(about_data["values_label"], "Values")
        self.assertEqual(about_data["process_label"], "How we work")
        self.assertTrue(about_data["testimonials_enabled"])
        self.assertEqual(
            about_data["testimonials_heading"],
            "Client perspectives",
        )
        self.assertEqual(
            [item["id"] for item in about_data["testimonials"]],
            [
                self.second_published_testimonial.pk,
                self.published_testimonial.pk,
            ],
        )
        self.assertEqual(
            set(about_data["hero_image"]),
            {"url", "width", "height", "alt"},
        )

        contact_data = responses[self.contact.pk]
        self.assertEqual(contact_data["eyebrow"], "Start a conversation")
        self.assertEqual(
            contact_data["intro"],
            "Tell us about the research communication you need.",
        )
        self.assertEqual(
            [block["type"] for block in contact_data["body"]],
            ["heading", "rich_text"],
        )
        self.assertEqual(about_data["hero_image"]["alt"], "The LaBio Media team")

    def test_service_related_work_is_selected_ordered_and_public(self):
        selected = CaseStudyPage(
            title="Second selected project",
            slug="second-selected-project",
            category="Editorial",
            summary="A second selected project.",
            hero_image=self.image,
            hero_image_alt="Second selected project",
        )
        self.portfolio_index.add_child(instance=selected)
        selected.save_revision().publish()
        selected.services.add(self.service)

        unselected = CaseStudyPage(
            title="Unselected project",
            slug="unselected-project",
            category="Editorial",
            summary="Related as a capability, but not editorially selected.",
            hero_image=self.image,
            hero_image_alt="Unselected project",
        )
        self.portfolio_index.add_child(instance=unselected)
        unselected.save_revision().publish()
        unselected.services.add(self.service)

        draft = CaseStudyPage(
            title="Draft selected project",
            slug="draft-selected-project",
            category="Editorial",
            summary="Draft content.",
            hero_image=self.image,
            hero_image_alt="Draft selected project",
            live=False,
        )
        self.portfolio_index.add_child(instance=draft)
        draft.save_revision()

        private = CaseStudyPage(
            title="Private selected project",
            slug="private-selected-project",
            category="Editorial",
            summary="Private content.",
            hero_image=self.image,
            hero_image_alt="Private selected project",
        )
        self.portfolio_index.add_child(instance=private)
        private.save_revision().publish()
        PageViewRestriction.objects.create(
            page=private,
            restriction_type=PageViewRestriction.LOGIN,
        )

        existing_relation = ServicePageRelatedCaseStudy.objects.get(
            page=self.service,
            case_study=self.case_study,
        )
        existing_relation.sort_order = 2
        existing_relation.save(update_fields=["sort_order"])
        ServicePageRelatedCaseStudy.objects.create(
            page=self.service,
            case_study=draft,
            sort_order=0,
        )
        ServicePageRelatedCaseStudy.objects.create(
            page=self.service,
            case_study=selected,
            sort_order=1,
        )
        ServicePageRelatedCaseStudy.objects.create(
            page=self.service,
            case_study=private,
            sort_order=3,
        )

        response = self.client.get(f"/api/cms/v2/pages/{self.service.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()["related_case_studies"]],
            [selected.pk, self.case_study.pk],
        )
        self.assertNotIn(
            unselected.pk,
            [item["id"] for item in response.json()["related_case_studies"]],
        )

    def test_service_editorial_sections_can_be_empty_or_disabled(self):
        Testimonial.objects.create(
            quote="Related globally but not selected.",
            person="Unselected Person",
            related_service=self.service,
            active=True,
            live=True,
        )
        ServicePageTestimonial.objects.filter(page=self.service).delete()
        response = self.client.get(f"/api/cms/v2/pages/{self.service.pk}/")

        self.assertTrue(response.json()["testimonials_enabled"])
        self.assertEqual(response.json()["testimonials"], [])

        self.service.testimonials_enabled = False
        self.service.related_work_enabled = False
        self.service.testimonials_heading = "Selected client perspectives"
        self.service.related_work_heading = "Selected projects"
        self.service.cta_heading = "Discuss your project"
        self.service.save_revision().publish()
        response = self.client.get(f"/api/cms/v2/pages/{self.service.pk}/")
        data = response.json()

        self.assertFalse(data["testimonials_enabled"])
        self.assertEqual(data["testimonials"], [])
        self.assertFalse(data["related_work_enabled"])
        self.assertEqual(data["related_case_studies"], [])
        self.assertEqual(
            data["testimonials_heading"],
            "Selected client perspectives",
        )
        self.assertEqual(data["related_work_heading"], "Selected projects")
        self.assertEqual(data["cta_heading"], "Discuss your project")

    def test_service_editorial_migration_backfills_existing_relationships(self):
        ServicePageRelatedCaseStudy.objects.filter(page=self.service).delete()
        ServicePageTestimonial.objects.filter(page=self.service).delete()
        migration = import_module(
            "public_content.migrations.0012_servicepage_cta_heading_and_more"
        )

        migration.backfill_service_editorial_selections(
            django_apps,
            SimpleNamespace(connection=connection),
        )

        self.assertEqual(
            list(
                ServicePageRelatedCaseStudy.objects.filter(page=self.service)
                .order_by("sort_order", "pk")
                .values_list("case_study_id", flat=True)
            ),
            [self.case_study.pk],
        )
        self.assertEqual(
            list(
                ServicePageTestimonial.objects.filter(page=self.service)
                .order_by("sort_order", "pk")
                .values_list("testimonial_id", flat=True)
            ),
            [self.second_published_testimonial.pk],
        )

    def test_case_study_editorial_fields_are_optional(self):
        minimal = CaseStudyPage(
            title="Minimal public project",
            slug="minimal-public-project",
            client_display_name="",
            category="Editorial",
            summary="",
            hero_image=self.image,
            hero_image_alt="Minimal public project",
        )
        self.portfolio_index.add_child(instance=minimal)
        minimal.save_revision().publish()

        response = self.client.get(f"/api/cms/v2/pages/{minimal.pk}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["client_display_name"], "")
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["project_year"], "")
        self.assertEqual(data["challenge"], "")
        self.assertEqual(data["approach"], "")
        self.assertEqual(data["deliverables"], [])
        self.assertEqual(data["outcome"], "")
        self.assertEqual(data["project_url"], "")
        self.assertEqual(data["cta_label"], "")
        self.assertEqual(data["cta_url"], "")
        self.assertEqual(data["showcase"], [])

    def test_case_study_showcase_serializes_controlled_ordered_modules(self):
        image_value = {
            "image": self.image,
            "alt_text": "A controlled showcase image",
            "caption": "Optional editorial caption",
        }
        image_without_caption = {
            "image": self.image,
            "alt_text": "A showcase image without a caption",
            "caption": "",
        }
        showcase = [
            (
                "photo_slider",
                {
                    "heading": "Photography",
                    "images": [image_value, image_value],
                },
            ),
            (
                "masonry_gallery",
                {
                    "heading": "Details",
                    "images": [image_value, image_value],
                },
            ),
            (
                "image_grid",
                {
                    "heading": "Applications",
                    "columns": "3",
                    "images": [image_without_caption],
                },
            ),
            (
                "image_pair",
                {
                    "heading": "Before and after",
                    "first_image": image_value,
                    "second_image": image_value,
                },
            ),
            (
                "video",
                {
                    "heading": "Research story",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "caption": "A consent-aware video.",
                },
            ),
            (
                "website_preview_grid",
                {
                    "heading": "Website views",
                    "items": [
                        {
                            "image": self.image,
                            "alt_text": "Website homepage preview",
                            "label": "Homepage",
                            "url": "https://example.com/project",
                            "caption": "Desktop view",
                        }
                    ],
                },
            ),
            (
                "wide_image",
                {
                    "heading": "Final composition",
                    "image": self.image,
                    "alt_text": "Final visual composition",
                    "caption": "Wide editorial image",
                },
            ),
        ]
        page = CaseStudyPage(
            title="Showcase project",
            slug="showcase-project",
            category="Mixed",
            hero_image=self.image,
            hero_image_alt="Showcase project",
            showcase=showcase,
        )
        self.portfolio_index.add_child(instance=page)
        page.save_revision().publish()

        response = self.client.get(f"/api/cms/v2/pages/{page.pk}/")

        self.assertEqual(response.status_code, 200)
        blocks = response.json()["showcase"]
        self.assertEqual(
            [block["type"] for block in blocks],
            [
                "photo_slider",
                "masonry_gallery",
                "image_grid",
                "image_pair",
                "video",
                "website_preview_grid",
                "wide_image",
            ],
        )
        slider_image = blocks[0]["value"]["images"][0]
        self.assertEqual(
            set(slider_image),
            {"url", "width", "height", "alt", "caption"},
        )
        self.assertEqual(slider_image["alt"], "A controlled showcase image")
        self.assertNotIn("file", slider_image)
        self.assertNotIn("original", slider_image)
        masonry_image = blocks[1]["value"]["images"][0]
        grid_image = blocks[2]["value"]["images"][0]
        pair_images = (
            blocks[3]["value"]["first_image"],
            blocks[3]["value"]["second_image"],
        )
        preview_image = blocks[5]["value"]["items"][0]["image"]
        wide_image = blocks[6]["value"]["image"]
        for image in (
            slider_image,
            masonry_image,
            grid_image,
            *pair_images,
            preview_image,
            wide_image,
        ):
            self.assertTrue(image["url"])
            self.assertGreater(image["width"], 0)
            self.assertGreater(image["height"], 0)
            self.assertTrue(image["alt"])
        self.assertNotIn("caption", grid_image)
        self.assertEqual(blocks[2]["value"]["columns"], "3")
        self.assertEqual(
            blocks[4]["value"]["url"],
            "https://www.youtube.com/watch?v=abc123",
        )
        preview = blocks[5]["value"]["items"][0]
        self.assertEqual(preview["label"], "Homepage")
        self.assertEqual(preview["url"], "https://example.com/project")
        self.assertEqual(
            set(blocks[6]["value"]["image"]),
            {"url", "width", "height", "alt"},
        )

    def test_case_study_showcase_validates_media_and_urls(self):
        showcase_block = CaseStudyShowcaseBlock()
        slider = showcase_block.child_blocks["photo_slider"]
        video = showcase_block.child_blocks["video"]
        website_preview = (
            showcase_block.child_blocks["website_preview_grid"]
            .child_blocks["items"]
            .child_block
        )

        with self.assertRaises(ValidationError):
            slider.clean(
                {
                    "heading": "Not enough slides",
                    "images": [
                        {
                            "image": self.image,
                            "alt_text": "Only one image",
                            "caption": "",
                        }
                    ],
                }
            )
        with self.assertRaises(ValidationError):
            video.clean(
                {
                    "heading": "Unsupported media",
                    "url": "https://example.com/video",
                    "caption": "",
                }
            )
        with self.assertRaises(ValidationError):
            website_preview.clean(
                {
                    "image": self.image,
                    "alt_text": "Website preview",
                    "label": "Unsafe link",
                    "url": "javascript:alert(1)",
                    "caption": "",
                }
            )

    def test_about_testimonial_selection_can_be_empty_or_disabled(self):
        AboutPageTestimonial.objects.filter(page=self.about).delete()
        response = self.client.get(f"/api/cms/v2/pages/{self.about.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["testimonials_enabled"])
        self.assertEqual(response.json()["testimonials"], [])

        AboutPageTestimonial.objects.create(
            page=self.about,
            testimonial=self.published_testimonial,
            sort_order=0,
        )
        self.about.testimonials_enabled = False
        self.about.save_revision().publish()
        response = self.client.get(f"/api/cms/v2/pages/{self.about.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["testimonials_enabled"])
        self.assertEqual(response.json()["testimonials"], [])

    def test_homepage_can_disable_collaborator_section(self):
        self.home.collaborators_enabled = False
        self.home.save_revision().publish()

        response = self.client.get(
            f"/api/cms/v2/pages/{self.home.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["collaborators_enabled"])

    def test_homepage_section_visibility_flags_are_public(self):
        for field_name in (
            "selected_work_enabled",
            "services_enabled",
            "testimonials_enabled",
            "about_enabled",
            "contact_enabled",
            "updates_enabled",
        ):
            setattr(self.home, field_name, False)
        self.home.save_revision().publish()

        response = self.client.get(
            f"/api/cms/v2/pages/{self.home.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        for field_name in (
            "selected_work_enabled",
            "services_enabled",
            "testimonials_enabled",
            "about_enabled",
            "contact_enabled",
            "updates_enabled",
        ):
            self.assertFalse(response.json()[field_name])

    def test_typed_page_listing_supports_frontend_fields_contract(self):
        response = self.client.get(
            "/api/cms/v2/pages/",
            {
                "type": "public_content.PricingPage",
                "fields": "*",
            },
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual([item["id"] for item in items], [self.pricing.pk])
        self.assertEqual(
            [item["id"] for item in items[0]["pricing_items"]],
            [self.pricing_first.pk, self.pricing_second.pk],
        )

    def test_pricing_api_excludes_inactive_items_and_preserves_order(self):
        response = self.client.get(
            f"/api/cms/v2/pages/{self.pricing.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        pricing_items = response.json()["pricing_items"]
        self.assertEqual(
            [item["id"] for item in pricing_items],
            [self.pricing_first.pk, self.pricing_second.pk],
        )
        self.assertEqual(
            set(pricing_items[0]),
            {
                "id",
                "title",
                "pricing_mode",
                "currency",
                "price_label",
                "description",
                "ideal_for",
                "features",
                "context",
                "cta_label",
                "cta_url",
                "featured",
                "related_services",
                "related_case_studies",
            },
        )
        self.assertEqual(
            pricing_items[0]["pricing_mode"],
            PricingItem.PricingMode.STARTING_FROM,
        )
        self.assertEqual(pricing_items[0]["currency"], "€")
        self.assertEqual(
            pricing_items[0]["ideal_for"],
            "Research teams building a reusable image library.",
        )
        self.assertEqual(
            pricing_items[0]["features"],
            ["Planning", "Edited delivery"],
        )
        self.assertEqual(
            pricing_items[0]["context"],
            "Travel and specialist production costs are scoped separately.",
        )
        self.assertTrue(pricing_items[0]["featured"])
        self.assertEqual(
            [item["id"] for item in pricing_items[0]["related_services"]],
            [self.service.pk],
        )
        self.assertEqual(
            [item["id"] for item in pricing_items[0]["related_case_studies"]],
            [self.case_study.pk],
        )
        self.assertEqual(
            pricing_items[1]["pricing_mode"],
            PricingItem.PricingMode.FIXED,
        )

    def test_pricing_optional_fields_and_custom_mode_remain_valid(self):
        hidden = PricingItem.objects.get(title="Hidden service")
        hidden.active = True
        hidden.sort_order = 3
        hidden.full_clean()
        hidden.save()

        response = self.client.get(f"/api/cms/v2/pages/{self.pricing.pk}/")

        self.assertEqual(response.status_code, 200)
        item = response.json()["pricing_items"][-1]
        self.assertEqual(item["pricing_mode"], PricingItem.PricingMode.CUSTOM)
        self.assertEqual(item["currency"], "")
        self.assertEqual(item["price_label"], "Contact us")
        self.assertEqual(item["ideal_for"], "")
        self.assertEqual(item["features"], [])
        self.assertEqual(item["context"], "")
        self.assertFalse(item["featured"])
        self.assertEqual(item["related_services"], [])
        self.assertEqual(item["related_case_studies"], [])

    def test_pricing_relations_exclude_draft_pages(self):
        draft_service = ServicePage(
            title="Draft service",
            slug="draft-service",
            live=False,
            summary="Not public.",
            cta_label="Contact",
            cta_url="https://example.com/contact",
        )
        self.service_index.add_child(instance=draft_service)
        draft_service.save_revision()
        draft_case_study = CaseStudyPage(
            title="Draft case study",
            slug="draft-case-study",
            live=False,
            category="Film",
            hero_image=self.image,
            hero_image_alt="Draft case study",
        )
        self.portfolio_index.add_child(instance=draft_case_study)
        draft_case_study.save_revision()
        self.pricing_first.related_services = [
            ("service", self.service),
            ("service", draft_service),
        ]
        self.pricing_first.related_case_studies = [
            ("case_study", self.case_study),
            ("case_study", draft_case_study),
        ]
        self.pricing_first.save()

        response = self.client.get(f"/api/cms/v2/pages/{self.pricing.pk}/")

        self.assertEqual(response.status_code, 200)
        item = response.json()["pricing_items"][0]
        self.assertEqual(
            [related["id"] for related in item["related_services"]],
            [self.service.pk],
        )
        self.assertEqual(
            [related["id"] for related in item["related_case_studies"]],
            [self.case_study.pk],
        )

    def test_unpublished_pricing_page_is_not_exposed(self):
        PricingPage.objects.filter(pk=self.pricing.pk).update(live=False)

        self.assertEqual(
            self.client.get(
                f"/api/cms/v2/pages/{self.pricing.pk}/"
            ).status_code,
            404,
        )

    def test_cms_api_contains_no_private_business_or_auth_metadata(self):
        responses = [
            self.client.get(
                f"/api/cms/v2/pages/{self.home.pk}/"
            ).json(),
            self.client.get("/api/cms/v2/collaborators/").json(),
            self.client.get("/api/cms/v2/testimonials/").json(),
            self.client.get("/api/cms/v2/settings/").json(),
        ]
        forbidden_keys = {
            "client",
            "project",
            "project_file",
            "approval",
            "conversation",
            "message",
            "user",
            "username",
            "email",
            "permissions",
            "groups",
            "provider_public_id",
            "provider_asset_id",
            "storage_key",
        }

        for response in responses:
            self.assertTrue(
                self._collect_keys(response).isdisjoint(forbidden_keys)
            )

    def test_existing_routes_resolve_to_expected_apps(self):
        self.assertTrue(
            resolve("/admin/").func.__module__.startswith("django.contrib.admin")
        )
        self.assertTrue(
            resolve("/cms/").func.__module__.startswith("wagtail.admin")
        )
        self.assertEqual(resolve("/api/cms/v2/").url_name, "cms-api-root")
        self.assertEqual(resolve("/api/projects/").url_name, "project-list")
        self.assertEqual(resolve("/health/").url_name, None)

        self.assertIn(self.client.get("/admin/").status_code, {302, 403})
        self.assertIn(self.client.get("/cms/").status_code, {302, 403})
        self.assertEqual(self.client.get("/api/").status_code, 200)
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/projects/").status_code, 401)

    def test_wagtail_image_and_document_indexes_are_not_public(self):
        self.assertEqual(
            self.client.get("/api/cms/v2/images/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/cms/v2/documents/").status_code,
            404,
        )

    def test_public_page_tree_rules_are_constrained(self):
        self.assertEqual(HomePage.max_count, 1)
        self.assertEqual(
            set(HomePage.subpage_types),
            {
                "public_content.ServiceIndexPage",
                "public_content.PortfolioIndexPage",
                "public_content.PricingPage",
                "public_content.AboutPage",
                "public_content.ContactPage",
                "public_content.UpdatesIndexPage",
                "public_content.StandardPage",
            },
        )
        self.assertEqual(ContactPage.parent_page_types, ["public_content.HomePage"])
        self.assertEqual(ContactPage.subpage_types, [])
        self.assertEqual(
            StandardPage.parent_page_types,
            ["public_content.HomePage", "public_content.StandardPage"],
        )
        self.assertEqual(
            StandardPage.subpage_types,
            ["public_content.StandardPage"],
        )


@override_settings(STORAGES=TEST_STORAGES)
class UpdatesContentAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        for existing_page in root.get_children():
            existing_page.delete()

        cls.site = Site.objects.filter(is_default_site=True).first()
        if cls.site is None:
            cls.site = Site.objects.create(
                hostname="testserver",
                port=80,
                root_page=root,
                is_default_site=True,
            )
        else:
            cls.site.hostname = "testserver"
            cls.site.port = 80

        cls.image = get_image_model().objects.create(
            title="Updates editorial image",
            file=SimpleUploadedFile(
                "updates.gif",
                ONE_PIXEL_GIF,
                content_type="image/gif",
            ),
        )
        cls.home = HomePage(
            title="LaBio Media",
            slug="home",
            hero_eyebrow="Creative production",
            hero_heading="Stories with impact",
            hero_copy="Public editorial copy.",
            hero_image=cls.image,
            hero_image_alt="A LaBio Media production",
            primary_cta_label="View work",
            primary_cta_url="https://example.com/work",
            secondary_cta_label="Contact",
            secondary_cta_url="https://example.com/contact",
            about_heading="About LaBio",
            about_copy="A public about teaser.",
            about_image=cls.image,
            about_image_alt="LaBio collaborators at work",
            contact_heading="Start a project",
            contact_copy="Public contact copy.",
            contact_cta_label="Get in touch",
            contact_cta_url="https://example.com/contact",
        )
        root.add_child(instance=cls.home)
        cls.home.save_revision().publish()
        cls.site.root_page = cls.home
        cls.site.save()

        cls.index = UpdatesIndexPage(
            title="Updates",
            slug="updates",
            seo_title="LaBio Media updates",
            search_description="Insights, milestones, updates and events.",
        )
        cls.home.add_child(instance=cls.index)
        cls.index.save_revision().publish()

        today = timezone.localdate()
        cls.newest_article = cls._add_article(
            title="Newest insight",
            slug="newest-insight",
            article_type=ArticlePage.ArticleType.INSIGHT,
            publication_date=today - timedelta(days=1),
            featured=True,
        )
        cls.older_article = cls._add_article(
            title="Earlier milestone",
            slug="earlier-milestone",
            article_type=ArticlePage.ArticleType.MILESTONE,
            publication_date=today - timedelta(days=10),
        )
        cls.draft_article = cls._add_article(
            title="Draft update",
            slug="draft-update",
            article_type=ArticlePage.ArticleType.UPDATE,
            publication_date=today,
            publish=False,
        )

        cls.nearest_event = cls._add_event(
            title="Nearest event",
            slug="nearest-event",
            start_date=today + timedelta(days=2),
            start_time=time(9, 30),
        )
        cls.later_event = cls._add_event(
            title="Later event",
            slug="later-event",
            start_date=today + timedelta(days=20),
            start_time=time(14, 0),
            end_date=today + timedelta(days=21),
            end_time=time(16, 0),
        )
        cls.past_event = cls._add_event(
            title="Past event",
            slug="past-event",
            start_date=today - timedelta(days=7),
            start_time=time(12, 0),
            end_date=today - timedelta(days=7),
            end_time=time(14, 0),
        )
        cls.draft_event = cls._add_event(
            title="Draft event",
            slug="draft-event",
            start_date=today + timedelta(days=1),
            publish=False,
        )
        published_at = timezone.now()
        for offset, page in enumerate(
            (
                cls.newest_article,
                cls.nearest_event,
                cls.older_article,
                cls.later_event,
                cls.past_event,
            )
        ):
            Page.objects.filter(pk=page.pk).update(
                first_published_at=published_at - timedelta(minutes=offset)
            )

    @classmethod
    def _add_article(
        cls,
        *,
        title,
        slug,
        article_type,
        publication_date,
        featured=False,
        publish=True,
    ):
        page = ArticlePage(
            title=title,
            slug=slug,
            article_type=article_type,
            summary=f"Summary for {title}.",
            featured_image=cls.image,
            featured_image_alt=f"Editorial image for {title}",
            publication_date=publication_date,
            featured=featured,
            body=[("rich_text", f"<p>Body for {title}.</p>")],
            seo_title=f"{title} | LaBio Media",
            search_description=f"Search description for {title}.",
            live=False,
        )
        cls.index.add_child(instance=page)
        revision = page.save_revision()
        if publish:
            revision.publish()
        return page

    @classmethod
    def _add_event(
        cls,
        *,
        title,
        slug,
        start_date,
        start_time=None,
        end_date=None,
        end_time=None,
        publish=True,
    ):
        page = EventPage(
            title=title,
            slug=slug,
            summary=f"Summary for {title}.",
            featured_image=cls.image,
            featured_image_alt=f"Editorial image for {title}",
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
            location="Helsinki, Finland",
            registration_url="https://example.com/register",
            featured=False,
            body=[("rich_text", f"<p>Body for {title}.</p>")],
            seo_title=f"{title} | LaBio Media",
            search_description=f"Search description for {title}.",
            live=False,
        )
        cls.index.add_child(instance=page)
        revision = page.save_revision()
        if publish:
            revision.publish()
        return page

    def test_updates_page_hierarchy_is_constrained(self):
        self.assertEqual(UpdatesIndexPage.max_count, 1)
        self.assertEqual(
            UpdatesIndexPage.parent_page_types,
            ["public_content.HomePage"],
        )
        self.assertEqual(
            set(UpdatesIndexPage.subpage_types),
            {"public_content.ArticlePage", "public_content.EventPage"},
        )
        self.assertEqual(
            ArticlePage.parent_page_types,
            ["public_content.UpdatesIndexPage"],
        )
        self.assertEqual(ArticlePage.subpage_types, [])
        self.assertEqual(
            EventPage.parent_page_types,
            ["public_content.UpdatesIndexPage"],
        )
        self.assertEqual(EventPage.subpage_types, [])

    def test_index_serializes_published_content_in_editorial_order(self):
        response = self.client.get(f"/api/cms/v2/pages/{self.index.pk}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            [item["id"] for item in data["articles"]],
            [self.newest_article.pk, self.older_article.pk],
        )
        self.assertEqual(
            [item["id"] for item in data["upcoming_events"]],
            [self.nearest_event.pk, self.later_event.pk],
        )
        self.assertEqual(
            [item["id"] for item in data["past_events"]],
            [self.past_event.pk],
        )
        exposed_ids = {
            item["id"]
            for field in ("articles", "upcoming_events", "past_events")
            for item in data[field]
        }
        self.assertNotIn(self.draft_article.pk, exposed_ids)
        self.assertNotIn(self.draft_event.pk, exposed_ids)

    def test_homepage_serializes_latest_published_updates_with_controls(self):
        response = self.client.get(f"/api/cms/v2/pages/{self.home.pk}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["updates_enabled"])
        self.assertEqual(data["updates_eyebrow"], "From LaBio")
        self.assertEqual(
            data["updates_heading"],
            "A few notes, ideas and milestones.",
        )
        self.assertEqual(data["updates_item_count"], 3)
        self.assertEqual(data["updates_cta_label"], "View all updates")
        self.assertEqual(
            data["updates_cta_url"],
            "https://labiomedia.com/updates",
        )
        self.assertEqual(
            [item["id"] for item in data["latest_updates"]],
            [
                self.newest_article.pk,
                self.nearest_event.pk,
                self.older_article.pk,
            ],
        )
        self.assertEqual(
            [item["kind"] for item in data["latest_updates"]],
            ["article", "event", "article"],
        )
        self.assertNotIn(
            self.draft_article.pk,
            [item["id"] for item in data["latest_updates"]],
        )

    def test_homepage_latest_updates_respects_count_and_disabled_state(self):
        self.home.updates_item_count = 1
        self.home.save_revision().publish()
        response = self.client.get(f"/api/cms/v2/pages/{self.home.pk}/")

        self.assertEqual(
            [item["id"] for item in response.json()["latest_updates"]],
            [self.newest_article.pk],
        )

        self.home.updates_enabled = False
        self.home.save_revision().publish()
        response = self.client.get(f"/api/cms/v2/pages/{self.home.pk}/")

        self.assertFalse(response.json()["updates_enabled"])
        self.assertEqual(response.json()["latest_updates"], [])

    def test_article_detail_uses_safe_existing_serialization(self):
        response = self.client.get(
            f"/api/cms/v2/pages/{self.newest_article.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["article_type"], "insight")
        self.assertEqual(data["summary"], "Summary for Newest insight.")
        self.assertTrue(data["featured"])
        self.assertEqual(
            set(data["featured_image"]),
            {"url", "width", "height", "alt"},
        )
        self.assertEqual(
            data["featured_image"]["alt"],
            "Editorial image for Newest insight",
        )
        self.assertEqual(data["body"][0]["type"], "rich_text")
        self.assertEqual(
            data["meta"]["seo_title"],
            "Newest insight | LaBio Media",
        )
        self.assertEqual(
            data["meta"]["search_description"],
            "Search description for Newest insight.",
        )

    def test_updates_allow_text_only_pages_without_featured_media(self):
        article = ArticlePage(
            title="Text-only update",
            slug="text-only-update",
            article_type=ArticlePage.ArticleType.UPDATE,
            summary="A complete update without media.",
            publication_date=timezone.localdate(),
            body=[("rich_text", "<p>Text-only body.</p>")],
            live=False,
        )
        self.index.add_child(instance=article)
        article.save_revision().publish()

        data = self.client.get(
            f"/api/cms/v2/pages/{article.pk}/"
        ).json()

        self.assertIsNone(data["featured_image"])
        self.assertEqual(data["showcase"], [])

    def test_update_showcase_reuses_controlled_media_blocks_for_articles_and_events(self):
        image_value = {
            "image": self.image,
            "alt_text": "Update showcase image",
            "caption": "Editorial media caption",
        }
        showcase = [
            (
                "masonry_gallery",
                {"heading": "Gallery", "images": [image_value, image_value]},
            ),
            (
                "image_grid",
                {"heading": "Grid", "columns": "2", "images": [image_value]},
            ),
            (
                "image_pair",
                {
                    "heading": "Pair",
                    "first_image": image_value,
                    "second_image": image_value,
                },
            ),
            (
                "video",
                {
                    "heading": "Video",
                    "url": "https://vimeo.com/123456",
                    "caption": "Consent-aware video",
                },
            ),
            (
                "wide_image",
                {
                    "heading": "Wide",
                    "image": self.image,
                    "alt_text": "Wide update image",
                    "caption": "Wide image caption",
                },
            ),
        ]

        for page in (self.newest_article, self.later_event):
            page.showcase = showcase
            page.save_revision().publish()
            data = self.client.get(
                f"/api/cms/v2/pages/{page.pk}/"
            ).json()
            self.assertEqual(
                [block["type"] for block in data["showcase"]],
                [
                    "masonry_gallery",
                    "image_grid",
                    "image_pair",
                    "video",
                    "wide_image",
                ],
            )
            self.assertEqual(
                data["showcase"][0]["value"]["images"][0]["alt"],
                "Update showcase image",
            )

        self.assertEqual(
            set(UpdateShowcaseBlock().child_blocks),
            {
                "masonry_gallery",
                "image_grid",
                "image_pair",
                "video",
                "wide_image",
            },
        )

    def test_event_detail_serializes_dates_location_and_registration(self):
        response = self.client.get(
            f"/api/cms/v2/pages/{self.later_event.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"], "Summary for Later event.")
        self.assertEqual(data["start_time"], "14:00:00")
        self.assertEqual(data["end_time"], "16:00:00")
        self.assertEqual(data["location"], "Helsinki, Finland")
        self.assertEqual(
            data["registration_url"],
            "https://example.com/register",
        )
        self.assertEqual(
            set(data["featured_image"]),
            {"url", "width", "height", "alt"},
        )
        self.assertEqual(data["body"][0]["type"], "rich_text")

    def test_drafts_are_hidden_but_past_events_remain_accessible(self):
        self.assertEqual(
            self.client.get(
                f"/api/cms/v2/pages/{self.draft_article.pk}/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/cms/v2/pages/{self.draft_event.pk}/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/cms/v2/pages/{self.past_event.pk}/"
            ).status_code,
            200,
        )

    def test_event_rejects_an_end_before_its_start(self):
        event = EventPage(
            title="Invalid event",
            summary="Invalid chronology.",
            featured_image=self.image,
            featured_image_alt="Invalid event image",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() - timedelta(days=1),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "End date cannot be before the start date.",
        ):
            event.clean()
