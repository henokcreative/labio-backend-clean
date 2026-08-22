import base64
from datetime import time, timedelta

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from clients.permissions import PORTAL_STAFF_PERMISSION
from .models import (
    AboutPage,
    ArticlePage,
    CaseStudyPage,
    Collaborator,
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
            hero_image=cls.image,
            hero_image_alt="Film production",
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
            hero_image=cls.image,
            hero_image_alt="A finished public production",
            embed_url="https://example.com/public-video",
            featured=True,
        )
        cls.portfolio_index.add_child(instance=cls.case_study)
        cls.case_study.services.add(cls.service)
        cls.case_study.save_revision().publish()

        cls.about = AboutPage(
            title="About",
            slug="about",
            hero_image=cls.image,
            hero_image_alt="The LaBio Media team",
            intro="Public about introduction.",
        )
        cls.home.add_child(instance=cls.about)
        cls.about.save_revision().publish()

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
            features=[("feature", "Planning"), ("feature", "Edited delivery")],
            cta_label="Request a quote",
            cta_url="https://example.com/contact",
            active=True,
            sort_order=0,
        )
        PricingItem.objects.create(
            page=cls.pricing,
            title="Hidden service",
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
            price_label="From €800",
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
        cls.home.save_revision().publish()

        SiteSettings.objects.create(
            site=cls.site,
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

    def test_settings_endpoint_exposes_only_public_fields(self):
        response = self.client.get("/api/cms/v2/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {
                "public_contact_email",
                "public_phone",
                "address",
                "default_cta_label",
                "default_cta_url",
                "social_links",
                "default_social_image",
            },
        )
        self.assertEqual(
            set(response.json()["default_social_image"]),
            {"url", "width", "height", "alt"},
        )

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
                "role",
                "organization",
                "related_service",
                "related_case_study",
            },
        )
        self.assertTrue(home_data["about_enabled"])
        self.assertEqual(home_data["about_eyebrow"], "About LaBio Media")
        self.assertEqual(home_data["about_cta_label"], "More about LaBio Media")
        self.assertEqual(
            home_data["about_cta_url"],
            "https://labiomedia.com/about",
        )
        self.assertTrue(home_data["contact_enabled"])
        self.assertEqual(home_data["contact_eyebrow"], "Contact")
        self.assertEqual(
            [
                item["id"]
                for item in responses[self.service.pk][
                    "related_case_studies"
                ]
            ],
            [self.case_study.pk],
        )
        self.assertEqual(
            [item["id"] for item in responses[self.case_study.pk]["services"]],
            [self.service.pk],
        )

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
                "price_label",
                "description",
                "features",
                "cta_label",
                "cta_url",
            },
        )
        self.assertEqual(
            pricing_items[0]["features"],
            ["Planning", "Edited delivery"],
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
                "public_content.UpdatesIndexPage",
                "public_content.StandardPage",
            },
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
