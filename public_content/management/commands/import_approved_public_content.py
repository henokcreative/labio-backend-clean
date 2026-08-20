import warnings
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from wagtail.images import get_image_model
from wagtail.models import Site

from public_content.approved_fallback_content import (
    ABOUT,
    ASSETS,
    CASE_STUDIES,
    COLLABORATORS,
    MOCK_PRICING_ITEMS,
    MOCK_TESTIMONIALS,
    PRICING,
    SERVICES,
    SITE_SETTINGS,
)
from public_content.models import (
    AboutPage,
    CaseStudyPage,
    Collaborator,
    HomePage,
    HomePageFeaturedCaseStudy,
    HomePageFeaturedService,
    PortfolioIndexPage,
    PricingItem,
    PricingPage,
    ServiceIndexPage,
    ServicePage,
    SiteSettings,
    Testimonial,
)


class Command(BaseCommand):
    APPLY_CONFIRMATION = "IMPORT_APPROVED_PUBLIC_CONTENT"
    BUNDLE_VERSION = "2026-08-20-v3"
    MAX_IMPORT_RASTER_PIXELS = 4_000_000
    help = (
        "Idempotently import the approved Next.js public fallbacks into the "
        "existing Wagtail HomePage tree."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--frontend-root",
            type=Path,
            default=Path(settings.BASE_DIR).parent / "labio-next",
            help="Path to the labio-next repository containing approved media.",
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the page tree and media sources without writing data.",
        )
        mode.add_argument(
            "--apply",
            action="store_true",
            help="Create or update the approved content.",
        )
        parser.add_argument(
            "--confirm",
            default="",
            help=(
                "Required with --apply. Must equal "
                f"{self.APPLY_CONFIRMATION}."
            ),
        )

    def handle(self, *args, **options):
        if (
            options["apply"]
            and options["confirm"] != self.APPLY_CONFIRMATION
        ):
            raise CommandError(
                "--apply requires --confirm " + self.APPLY_CONFIRMATION
            )

        self.frontend_root = options["frontend_root"].expanduser().resolve()
        self.stdout.write(f"Import bundle version: {self.BUNDLE_VERSION}")
        self.stats = {
            "images_created": 0,
            "images_reused": 0,
            "pages_created": 0,
            "pages_updated": 0,
            "collaborators_created": 0,
            "collaborators_updated": 0,
            "pricing_items_created": 0,
            "pricing_items_updated": 0,
            "testimonials_created": 0,
            "testimonials_updated": 0,
        }

        # Prove and validate the exact runtime bundle before any database or
        # object-storage write can occur.
        self._validate_sources()
        home = self._get_home_page()
        site = self._get_site(home)
        self._validate_tree(home)

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry run passed: approved content, media sources, and page "
                    "tree are valid."
                )
            )
            return

        with transaction.atomic():
            # Wagtail image inspection can decode source media. Import each
            # file sequentially so only one source is processed at a time.
            images = {}
            for key in ASSETS:
                images[key] = self._get_or_create_image(key)

            service_index = self._upsert_page(
                home,
                ServiceIndexPage,
                "services",
                title="Services",
                intro=[],
            )
            services = self._upsert_services(service_index, images)

            portfolio_index = self._upsert_page(
                home,
                PortfolioIndexPage,
                "work",
                title="Work",
                intro=[],
            )
            case_studies = self._upsert_case_studies(
                portfolio_index,
                services,
                images,
            )

            self._upsert_page(
                home,
                AboutPage,
                "about",
                title=ABOUT["title"],
                hero_image=images[ABOUT["hero_asset"]],
                hero_image_alt=ABOUT["hero_alt"],
                intro=ABOUT["intro"],
                body=list(ABOUT["body"]),
                values=[],
                process=[],
                seo_title=ABOUT["seo_title"],
                search_description=ABOUT["search_description"],
            )

            pricing = self._upsert_page(
                home,
                PricingPage,
                "pricing",
                title=PRICING["title"],
                intro=PRICING["intro"],
                positioning_message=PRICING["positioning_message"],
            )
            self._upsert_pricing_items(pricing)

            self._upsert_home_relations(home, services, case_studies)
            self._upsert_collaborators(images)
            self._upsert_testimonials(services, case_studies)
            self._upsert_site_settings(site)

        summary = ", ".join(
            f"{name.replace('_', ' ')}: {value}"
            for name, value in self.stats.items()
        )
        self.stdout.write(self.style.SUCCESS(f"Approved content imported ({summary})."))

    @staticmethod
    def _get_home_page():
        homes = list(HomePage.objects.live().public())
        if len(homes) != 1:
            raise CommandError(
                "Expected exactly one live public HomePage; "
                f"found {len(homes)}."
            )
        return homes[0]

    @staticmethod
    def _get_site(home):
        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            raise CommandError("A default Wagtail Site record is required.")
        if not (
            site.root_page_id == home.pk
            or home.is_descendant_of(site.root_page)
        ):
            raise CommandError(
                "The live HomePage is outside the default Wagtail Site tree."
            )
        return site

    def _validate_sources(self):
        missing = []
        invalid_rasters = []
        oversized_rasters = []
        raster_details = []
        for relative_path, _title in ASSETS.values():
            source = self.frontend_root / relative_path
            if not source.is_file():
                missing.append(str(source))
                continue
            if source.suffix.lower() == ".svg":
                continue

            try:
                # Image.open reads only enough data for metadata here; it does
                # not decode the raster. Suppress Pillow's much higher default
                # warning because this command enforces a stricter limit.
                with warnings.catch_warnings():
                    warnings.simplefilter(
                        "ignore",
                        Image.DecompressionBombWarning,
                    )
                    with Image.open(source) as raster:
                        width, height = raster.size
            except (OSError, UnidentifiedImageError) as error:
                invalid_rasters.append(f"{source}: {error}")
                continue

            pixels = width * height
            filesize = source.stat().st_size
            detail = (
                f"{relative_path} | {width}x{height} | "
                f"{pixels:,} pixels | {filesize:,} bytes"
            )
            raster_details.append(detail)
            if pixels > self.MAX_IMPORT_RASTER_PIXELS:
                oversized_rasters.append(detail)
        for detail in raster_details:
            self.stdout.write(f"Import raster: {detail}")
        if missing:
            raise CommandError(
                "Approved media files are missing:\n" + "\n".join(missing)
            )
        if invalid_rasters:
            raise CommandError(
                "Approved raster media could not be inspected:\n"
                + "\n".join(invalid_rasters)
            )
        if oversized_rasters:
            raise CommandError(
                "Approved raster media exceeds the 4,000,000-pixel import "
                "limit:\n" + "\n".join(oversized_rasters)
            )

    def _validate_tree(self, home):
        expected = (
            (home, "services", ServiceIndexPage),
            (home, "work", PortfolioIndexPage),
            (home, "about", AboutPage),
            (home, "pricing", PricingPage),
        )
        for parent, slug, model in expected:
            self._validate_child_type(parent, slug, model)

        service_index = self._specific_child(home, "services")
        if service_index is not None:
            for service in SERVICES:
                self._validate_child_type(
                    service_index,
                    service["slug"],
                    ServicePage,
                )

        portfolio_index = self._specific_child(home, "work")
        if portfolio_index is not None:
            for case_study in CASE_STUDIES:
                self._validate_child_type(
                    portfolio_index,
                    case_study["slug"],
                    CaseStudyPage,
                )

    def _validate_child_type(self, parent, slug, model):
        child = self._specific_child(parent, slug)
        if child is not None and not isinstance(child, model):
            raise CommandError(
                f"Page '{slug}' below '{parent.slug}' is "
                f"{type(child).__name__}, expected {model.__name__}."
            )

    @staticmethod
    def _specific_child(parent, slug):
        child = parent.get_children().filter(slug=slug).first()
        return child.specific if child is not None else None

    def _get_or_create_image(self, asset_key):
        relative_path, title = ASSETS[asset_key]
        image_model = get_image_model()
        image = image_model.objects.filter(title=title).order_by("pk").first()
        if image is not None:
            self.stats["images_reused"] += 1
            return image

        source = self.frontend_root / relative_path
        image = image_model(title=title)
        with source.open("rb") as source_file:
            image.file.save(source.name, File(source_file), save=False)
        try:
            image.full_clean()
            image.save()
        finally:
            image.file.close()
        self.stats["images_created"] += 1
        return image

    def _upsert_page(self, parent, model, slug, **fields):
        page = self._specific_child(parent, slug)
        created = page is None
        if created:
            page = model(slug=slug, live=False, **fields)
            parent.add_child(instance=page)
        else:
            for field_name, value in fields.items():
                setattr(page, field_name, value)

        page.full_clean()
        page.save_revision().publish()
        self.stats["pages_created" if created else "pages_updated"] += 1
        return page

    def _upsert_services(self, service_index, images):
        services = {}
        for content in SERVICES:
            capabilities = [
                (
                    "capability",
                    {"title": title, "description": description},
                )
                for title, description in content["capabilities"]
            ]
            service = self._upsert_page(
                service_index,
                ServicePage,
                content["slug"],
                title=content["title"],
                summary=content["summary"],
                hero_image=images[content["hero_asset"]],
                hero_image_alt=content["hero_alt"],
                body=[],
                capabilities=capabilities,
                process=[],
                cta_label=content["cta_label"],
                cta_url=content["cta_url"],
            )
            services[content["slug"]] = service
        return services

    def _upsert_case_studies(self, portfolio_index, services, images):
        case_studies = {}
        for content in CASE_STUDIES:
            body = [
                (
                    "heading",
                    {"text": "The challenge", "level": "h2"},
                ),
                ("rich_text", f"<p>{content['challenge']}</p>"),
                (
                    "heading",
                    {"text": "The approach", "level": "h2"},
                ),
                ("rich_text", f"<p>{content['approach']}</p>"),
            ]
            gallery = [
                (
                    "image",
                    {
                        "image": images[asset_key],
                        "alt_text": alt_text,
                        "caption": "",
                    },
                )
                for asset_key, alt_text in content["gallery"]
            ]
            case_study = self._upsert_page(
                portfolio_index,
                CaseStudyPage,
                content["slug"],
                title=content["title"],
                client_display_name=content["title"],
                category=content["category"],
                summary=content["summary"],
                body=body,
                hero_image=images[content["hero_asset"]],
                hero_image_alt=content["title"],
                gallery=gallery,
                embed_url="",
                publication_date=None,
                featured=True,
            )
            case_study.services.set(
                [services[slug] for slug in content["service_slugs"]]
            )
            case_study.full_clean()
            case_study.save_revision().publish()
            case_studies[content["slug"]] = case_study
        return case_studies

    @staticmethod
    def _replace_ordered_relations(manager, relation_model, page, field, values):
        manager.all().delete()
        relation_model.objects.bulk_create(
            [
                relation_model(
                    page=page,
                    sort_order=index,
                    **{field: value},
                )
                for index, value in enumerate(values)
            ]
        )

    def _upsert_home_relations(self, home, services, case_studies):
        self._replace_ordered_relations(
            home.featured_services,
            HomePageFeaturedService,
            home,
            "service",
            [services[content["slug"]] for content in SERVICES],
        )
        self._replace_ordered_relations(
            home.selected_case_studies,
            HomePageFeaturedCaseStudy,
            home,
            "case_study",
            [case_studies[content["slug"]] for content in CASE_STUDIES],
        )
        home.save_revision().publish()

    def _upsert_collaborators(self, images):
        for content in COLLABORATORS:
            collaborator = Collaborator.objects.filter(
                organization_name=content["organization_name"]
            ).first()
            created = collaborator is None
            if created:
                collaborator = Collaborator(
                    organization_name=content["organization_name"]
                )
            collaborator.logo = images[content["asset"]]
            collaborator.logo_alt = content["logo_alt"]
            collaborator.url = content["url"]
            collaborator.display_order = content["display_order"]
            collaborator.visual_variant = "default"
            collaborator.active = True
            collaborator.full_clean()
            collaborator.save()
            collaborator.save_revision().publish()
            key = "collaborators_created" if created else "collaborators_updated"
            self.stats[key] += 1

    def _upsert_pricing_items(self, pricing):
        for index, content in enumerate(MOCK_PRICING_ITEMS):
            item = PricingItem.objects.filter(
                page=pricing,
                title=content["title"],
            ).first()
            created = item is None
            if created:
                item = PricingItem(page=pricing, title=content["title"])
            item.price_label = content["price_label"]
            item.description = content["description"]
            item.features = [
                ("feature", feature)
                for feature in content["features"]
            ]
            item.cta_label = "Request a quote"
            item.cta_url = "https://labiomedia.com/contact"
            item.active = True
            item.sort_order = index
            item.full_clean()
            item.save()
            key = "pricing_items_created" if created else "pricing_items_updated"
            self.stats[key] += 1
        pricing.save_revision().publish()

    def _upsert_testimonials(self, services, case_studies):
        for content in MOCK_TESTIMONIALS:
            testimonial = Testimonial.objects.filter(
                person=content["person"]
            ).first()
            created = testimonial is None
            if created:
                testimonial = Testimonial(person=content["person"])
            testimonial.quote = content["quote"]
            testimonial.role = content["role"]
            testimonial.organization = content["organization"]
            testimonial.related_service = services.get(
                content.get("related_service_slug")
            )
            testimonial.related_case_study = case_studies.get(
                content.get("related_case_study_slug")
            )
            testimonial.active = True
            testimonial.full_clean()
            testimonial.save()
            testimonial.save_revision().publish()
            key = "testimonials_created" if created else "testimonials_updated"
            self.stats[key] += 1

    @staticmethod
    def _upsert_site_settings(site):
        site_settings, _created = SiteSettings.objects.get_or_create(site=site)
        for field_name, value in SITE_SETTINGS.items():
            setattr(site_settings, field_name, value)
        site_settings.full_clean()
        site_settings.save()
