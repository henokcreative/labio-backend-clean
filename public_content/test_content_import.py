import base64
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from .approved_fallback_content import ASSETS
from .models import (
    AboutPage,
    CaseStudyPage,
    Collaborator,
    HomePage,
    PortfolioIndexPage,
    PricingItem,
    PricingPage,
    ServiceIndexPage,
    ServicePage,
    SiteSettings,
    Testimonial,
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
MINIMAL_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"
viewBox="0 0 10 10"><rect width="10" height="10" fill="#000"/></svg>"""


@override_settings(STORAGES=TEST_STORAGES)
class ApprovedPublicContentImportTests(TestCase):
    def setUp(self):
        root = Page.get_first_root_node()
        for existing_page in root.get_children():
            existing_page.delete()

        home_image = get_image_model().objects.create(
            title="Existing production homepage image",
            file=SimpleUploadedFile(
                "home.gif",
                ONE_PIXEL_GIF,
                content_type="image/gif",
            ),
        )
        self.home = HomePage(
            title="LaBioMedia",
            slug="labiomedia",
            hero_eyebrow="Research communication",
            hero_heading="Existing production homepage",
            hero_copy="This content must remain unchanged.",
            hero_image=home_image,
            hero_image_alt="Existing homepage image",
            primary_cta_label="View work",
            primary_cta_url="https://labiomedia.com/work",
            secondary_cta_label="Services",
            secondary_cta_url="https://labiomedia.com/services",
            about_heading="Existing about heading",
            about_copy="Existing about copy.",
            about_image=home_image,
            about_image_alt="Existing about image",
            contact_heading="Existing contact heading",
            contact_copy="Existing contact copy.",
            contact_cta_label="Contact",
            contact_cta_url="https://labiomedia.com/contact",
        )
        root.add_child(instance=self.home)
        self.home.save_revision().publish()

        self.site = Site.objects.create(
            hostname="testserver",
            port=80,
            root_page=self.home,
            is_default_site=True,
        )

        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.frontend_root = Path(temporary_directory.name)
        for relative_path, _title in ASSETS.values():
            source = self.frontend_root / relative_path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(
                MINIMAL_SVG if source.suffix.lower() == ".svg" else ONE_PIXEL_GIF
            )

    def run_import(self, *, dry_run=False):
        output = StringIO()
        options = {
            "frontend_root": self.frontend_root,
            "stdout": output,
        }
        if dry_run:
            options["dry_run"] = True
        else:
            options["apply"] = True
            options["confirm"] = "IMPORT_APPROVED_PUBLIC_CONTENT"
        call_command("import_approved_public_content", **options)
        return output.getvalue()

    def test_dry_run_validates_without_writing(self):
        output = self.run_import(dry_run=True)

        self.assertIn("Dry run passed", output)
        self.assertEqual(ServiceIndexPage.objects.count(), 0)
        self.assertEqual(Collaborator.objects.count(), 0)
        self.assertFalse(SiteSettings.objects.filter(site=self.site).exists())

    def test_apply_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(
            CommandError,
            "--apply requires --confirm IMPORT_APPROVED_PUBLIC_CONTENT",
        ):
            call_command(
                "import_approved_public_content",
                frontend_root=self.frontend_root,
                apply=True,
                confirm="",
            )

    def test_apply_rejects_oversized_raster_before_writing(self):
        relative_path, _title = ASSETS["web-digital"]
        source = self.frontend_root / relative_path
        with Image.new("1", (3000, 3000)) as oversized:
            oversized.save(source, format="PNG")

        with self.assertRaisesMessage(
            CommandError,
            "3000x3000 (9,000,000 pixels)",
        ):
            call_command(
                "import_approved_public_content",
                frontend_root=self.frontend_root,
                apply=True,
                confirm="IMPORT_APPROVED_PUBLIC_CONTENT",
            )

        self.assertEqual(ServiceIndexPage.objects.count(), 0)
        self.assertEqual(get_image_model().objects.count(), 1)

    def test_import_is_idempotent_and_public_api_ready(self):
        original_home_copy = self.home.hero_copy
        first_output = self.run_import()

        self.assertIn("pages created: 11", first_output)
        self.assertEqual(ServiceIndexPage.objects.count(), 1)
        self.assertEqual(ServicePage.objects.count(), 4)
        self.assertEqual(PortfolioIndexPage.objects.count(), 1)
        self.assertEqual(CaseStudyPage.objects.count(), 3)
        self.assertEqual(AboutPage.objects.count(), 1)
        self.assertEqual(PricingPage.objects.count(), 1)
        self.assertEqual(PricingItem.objects.count(), 3)
        self.assertEqual(Testimonial.objects.filter(live=True, active=True).count(), 3)
        self.assertTrue(
            all(
                item.title.startswith("[MOCK]")
                for item in PricingItem.objects.all()
            )
        )
        self.assertTrue(
            all(
                testimonial.person.startswith("[MOCK]")
                for testimonial in Testimonial.objects.all()
            )
        )

        self.home.refresh_from_db()
        self.assertEqual(self.home.hero_copy, original_home_copy)
        self.assertEqual(
            list(
                self.home.featured_services.values_list(
                    "service__slug",
                    flat=True,
                )
            ),
            ["web-digital", "video-production", "photography", "brand-design"],
        )
        self.assertEqual(
            list(
                self.home.selected_case_studies.values_list(
                    "case_study__slug",
                    flat=True,
                )
            ),
            [
                "turku-bioscience",
                "research-storytelling",
                "laboratory-photography",
            ],
        )

        relationship_map = {
            page.slug: set(page.services.values_list("slug", flat=True))
            for page in CaseStudyPage.objects.all()
        }
        self.assertEqual(
            relationship_map,
            {
                "turku-bioscience": {"web-digital", "brand-design"},
                "research-storytelling": {"video-production"},
                "laboratory-photography": {"photography", "brand-design"},
            },
        )

        self.assertEqual(Collaborator.objects.filter(live=True, active=True).count(), 5)
        site_settings = SiteSettings.objects.get(site=self.site)
        self.assertEqual(site_settings.address, "Turku, Finland")
        self.assertEqual(site_settings.default_cta_label, "Start a conversation")

        page_response = self.client.get(
            "/api/cms/v2/pages/",
            {"fields": "*", "limit": 20},
        )
        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(page_response.json()["meta"]["total_count"], 12)
        collaborator_response = self.client.get("/api/cms/v2/collaborators/")
        self.assertEqual(collaborator_response.status_code, 200)
        self.assertEqual(len(collaborator_response.json()), 5)
        testimonial_response = self.client.get("/api/cms/v2/testimonials/")
        self.assertEqual(testimonial_response.status_code, 200)
        self.assertEqual(len(testimonial_response.json()), 3)
        settings_response = self.client.get("/api/cms/v2/settings/")
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(settings_response.json()["address"], "Turku, Finland")

        image_count = get_image_model().objects.count()
        page_count = Page.objects.count()
        collaborator_count = Collaborator.objects.count()
        pricing_item_count = PricingItem.objects.count()
        testimonial_count = Testimonial.objects.count()
        second_output = self.run_import()

        self.assertIn("pages created: 0", second_output)
        self.assertEqual(get_image_model().objects.count(), image_count)
        self.assertEqual(Page.objects.count(), page_count)
        self.assertEqual(Collaborator.objects.count(), collaborator_count)
        self.assertEqual(PricingItem.objects.count(), pricing_item_count)
        self.assertEqual(Testimonial.objects.count(), testimonial_count)
