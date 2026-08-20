from django.db import models
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail import blocks as wagtail_blocks
from wagtail.admin.panels import FieldPanel, InlinePanel, PublishingPanel
from wagtail.api import APIField
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.models import DraftStateMixin, Orderable, Page, RevisionMixin
from wagtail.snippets.models import register_snippet

from .api_fields import (
    ActivePricingItemsField,
    ControlledImageRenditionField,
    OrderedCollaboratorsField,
    OrderedRelatedPagesField,
    PublicPageListField,
)
from .blocks import (
    CapabilityBlock,
    GalleryImageBlock,
    ProcessStepBlock,
    PublicBodyBlock,
    SocialLinkBlock,
    ValueBlock,
)


class PublicSEOMixin(models.Model):
    social_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True

    seo_api_fields = [
        APIField(
            "social_image",
            serializer=ControlledImageRenditionField(
                "social_image",
                filter_spec="fill-1200x630",
            ),
        ),
    ]


class HeadlessPageMixin:
    preview_modes = []


class HomePage(HeadlessPageMixin, PublicSEOMixin, Page):
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = [
        "public_content.ServiceIndexPage",
        "public_content.PortfolioIndexPage",
        "public_content.AboutPage",
        "public_content.PricingPage",
        "public_content.StandardPage",
    ]

    hero_eyebrow = models.CharField(max_length=150)
    hero_heading = models.TextField(max_length=500)
    hero_copy = models.TextField(max_length=1000)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_alt = models.CharField(max_length=255)
    primary_cta_label = models.CharField(max_length=100)
    primary_cta_url = models.URLField(max_length=500)
    secondary_cta_label = models.CharField(max_length=100)
    secondary_cta_url = models.URLField(max_length=500)
    collaborators_enabled = models.BooleanField(
        default=True,
        help_text="Show the collaborators section on the public homepage.",
    )
    collaborators_heading = models.CharField(
        max_length=255,
        default="Trusted by research groups and organisations",
    )
    about_heading = models.CharField(max_length=255)
    about_copy = models.TextField(max_length=1500)
    about_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    about_image_alt = models.CharField(max_length=255)
    contact_heading = models.CharField(max_length=255)
    contact_copy = models.TextField(max_length=1000)
    contact_cta_label = models.CharField(max_length=100)
    contact_cta_url = models.URLField(max_length=500)

    content_panels = Page.content_panels + [
        FieldPanel("hero_eyebrow"),
        FieldPanel("hero_heading"),
        FieldPanel("hero_copy"),
        FieldPanel("hero_image"),
        FieldPanel("hero_image_alt"),
        FieldPanel("primary_cta_label"),
        FieldPanel("primary_cta_url"),
        FieldPanel("secondary_cta_label"),
        FieldPanel("secondary_cta_url"),
        InlinePanel("selected_case_studies", label="Selected case study"),
        InlinePanel("featured_services", label="Featured service"),
        FieldPanel("collaborators_enabled"),
        FieldPanel("collaborators_heading"),
        InlinePanel(
            "homepage_collaborators",
            label="Collaborator",
            help_text="Choose and drag collaborators into public display order.",
        ),
        FieldPanel("about_heading"),
        FieldPanel("about_copy"),
        FieldPanel("about_image"),
        FieldPanel("about_image_alt"),
        FieldPanel("contact_heading"),
        FieldPanel("contact_copy"),
        FieldPanel("contact_cta_label"),
        FieldPanel("contact_cta_url"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]

    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("hero_eyebrow"),
        APIField("hero_heading"),
        APIField("hero_copy"),
        APIField(
            "hero_image",
            serializer=ControlledImageRenditionField(
                "hero_image",
                "hero_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("primary_cta_label"),
        APIField("primary_cta_url"),
        APIField("secondary_cta_label"),
        APIField("secondary_cta_url"),
        APIField(
            "selected_work",
            serializer=OrderedRelatedPagesField(
                page_attribute="case_study",
                source="selected_case_studies",
            ),
        ),
        APIField(
            "featured_services",
            serializer=OrderedRelatedPagesField(
                page_attribute="service",
            ),
        ),
        APIField("collaborators_enabled"),
        APIField("collaborators_heading"),
        APIField(
            "collaborators",
            serializer=OrderedCollaboratorsField(
                source="homepage_collaborators",
            ),
        ),
        APIField("about_heading"),
        APIField("about_copy"),
        APIField(
            "about_image",
            serializer=ControlledImageRenditionField(
                "about_image",
                "about_image_alt",
                "fill-1200x900",
            ),
        ),
        APIField("contact_heading"),
        APIField("contact_copy"),
        APIField("contact_cta_label"),
        APIField("contact_cta_url"),
    ]


class ServiceIndexPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.HomePage"]
    subpage_types = ["public_content.ServicePage"]

    intro = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [APIField("intro")]


class ServicePage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.ServiceIndexPage"]
    subpage_types = []

    summary = models.TextField(max_length=1000)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_alt = models.CharField(max_length=255)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)
    capabilities = StreamField(
        [("capability", CapabilityBlock())],
        blank=True,
        use_json_field=True,
    )
    process = StreamField(
        [("step", ProcessStepBlock())],
        blank=True,
        use_json_field=True,
    )
    cta_label = models.CharField(max_length=100)
    cta_url = models.URLField(max_length=500)

    @property
    def published_related_case_studies(self):
        return CaseStudyPage.objects.live().public().filter(services=self)

    content_panels = Page.content_panels + [
        FieldPanel("summary"),
        FieldPanel("hero_image"),
        FieldPanel("hero_image_alt"),
        FieldPanel("body"),
        FieldPanel("capabilities"),
        FieldPanel("process"),
        FieldPanel("cta_label"),
        FieldPanel("cta_url"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("summary"),
        APIField(
            "hero_image",
            serializer=ControlledImageRenditionField(
                "hero_image",
                "hero_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("body"),
        APIField("capabilities"),
        APIField("process"),
        APIField("cta_label"),
        APIField("cta_url"),
        APIField(
            "related_case_studies",
            serializer=PublicPageListField(
                source="published_related_case_studies",
            ),
        ),
    ]


class PortfolioIndexPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.HomePage"]
    subpage_types = ["public_content.CaseStudyPage"]

    intro = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [APIField("intro")]


class CaseStudyPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.PortfolioIndexPage"]
    subpage_types = []

    client_display_name = models.CharField(max_length=255)
    category = models.CharField(max_length=150)
    summary = models.TextField(max_length=1000)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_alt = models.CharField(max_length=255)
    gallery = StreamField(
        [("image", GalleryImageBlock())],
        blank=True,
        use_json_field=True,
    )
    embed_url = models.URLField(max_length=500, blank=True)
    services = ParentalManyToManyField(
        "public_content.ServicePage",
        blank=True,
        related_name="case_studies",
    )
    publication_date = models.DateField(null=True, blank=True)
    featured = models.BooleanField(default=False)

    content_panels = Page.content_panels + [
        FieldPanel("client_display_name"),
        FieldPanel("category"),
        FieldPanel("summary"),
        FieldPanel("body"),
        FieldPanel("hero_image"),
        FieldPanel("hero_image_alt"),
        FieldPanel("gallery"),
        FieldPanel("embed_url"),
        FieldPanel("services"),
        FieldPanel("publication_date"),
        FieldPanel("featured"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("client_display_name"),
        APIField("category"),
        APIField("summary"),
        APIField("body"),
        APIField(
            "hero_image",
            serializer=ControlledImageRenditionField(
                "hero_image",
                "hero_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("gallery"),
        APIField("embed_url"),
        APIField("services", serializer=PublicPageListField()),
        APIField("publication_date"),
        APIField("featured"),
    ]


class AboutPage(HeadlessPageMixin, PublicSEOMixin, Page):
    max_count = 1
    parent_page_types = ["public_content.HomePage"]
    subpage_types = []

    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_alt = models.CharField(max_length=255)
    intro = models.TextField(max_length=1500)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)
    values = StreamField(
        [("value", ValueBlock())],
        blank=True,
        use_json_field=True,
    )
    process = StreamField(
        [("step", ProcessStepBlock())],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero_image"),
        FieldPanel("hero_image_alt"),
        FieldPanel("intro"),
        FieldPanel("body"),
        FieldPanel("values"),
        FieldPanel("process"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField(
            "hero_image",
            serializer=ControlledImageRenditionField(
                "hero_image",
                "hero_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("intro"),
        APIField("body"),
        APIField("values"),
        APIField("process"),
    ]


class StandardPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.HomePage", "public_content.StandardPage"]
    subpage_types = ["public_content.StandardPage"]

    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("body")]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [APIField("body")]


class PricingPage(HeadlessPageMixin, PublicSEOMixin, Page):
    max_count = 1
    parent_page_types = ["public_content.HomePage"]
    subpage_types = []

    intro = models.TextField(
        max_length=1500,
        help_text="A short introduction to LaBio Media's pricing approach.",
    )
    positioning_message = models.TextField(
        max_length=1500,
        help_text=(
            "Explain that projects are scoped individually and note any "
            "custom-pricing eligibility."
        ),
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        InlinePanel(
            "pricing_items",
            label="Pricing item",
            help_text="Drag items to set their public display order.",
        ),
        FieldPanel("positioning_message"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("intro"),
        APIField(
            "pricing_items",
            serializer=ActivePricingItemsField(),
        ),
        APIField("positioning_message"),
    ]


class PricingItem(Orderable):
    page = ParentalKey(
        PricingPage,
        related_name="pricing_items",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    price_label = models.CharField(
        max_length=100,
        help_text='Editorial text such as "From €400".',
    )
    description = models.TextField(max_length=1000)
    features = StreamField(
        [
            (
                "feature",
                wagtail_blocks.CharBlock(
                    max_length=255,
                    label="Included feature",
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )
    cta_label = models.CharField(max_length=100)
    cta_url = models.URLField(
        max_length=500,
        help_text="Use the full public destination URL.",
    )
    active = models.BooleanField(
        default=True,
        help_text="Inactive items stay in the CMS but are hidden publicly.",
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("price_label"),
        FieldPanel("description"),
        FieldPanel("features"),
        FieldPanel("cta_label"),
        FieldPanel("cta_url"),
        FieldPanel("active"),
    ]

    def __str__(self):
        return self.title


class HomePageFeaturedCaseStudy(Orderable):
    page = ParentalKey(
        HomePage,
        related_name="selected_case_studies",
        on_delete=models.CASCADE,
    )
    case_study = models.ForeignKey(
        CaseStudyPage,
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [FieldPanel("case_study")]


class HomePageFeaturedService(Orderable):
    page = ParentalKey(
        HomePage,
        related_name="featured_services",
        on_delete=models.CASCADE,
    )
    service = models.ForeignKey(
        ServicePage,
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [FieldPanel("service")]


class HomePageCollaborator(Orderable):
    page = ParentalKey(
        HomePage,
        related_name="homepage_collaborators",
        on_delete=models.CASCADE,
    )
    collaborator = models.ForeignKey(
        "public_content.Collaborator",
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [FieldPanel("collaborator")]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "collaborator"],
                name="unique_homepage_collaborator",
            )
        ]


@register_snippet
class Collaborator(DraftStateMixin, RevisionMixin, models.Model):
    organization_name = models.CharField(max_length=255)
    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    logo_alt = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    visual_variant = models.CharField(max_length=100, blank=True)

    panels = [
        FieldPanel("organization_name"),
        FieldPanel("logo"),
        FieldPanel("logo_alt"),
        FieldPanel("url"),
        FieldPanel("display_order"),
        FieldPanel("active"),
        FieldPanel("visual_variant"),
        PublishingPanel(),
    ]

    class Meta:
        ordering = ["display_order", "organization_name"]

    def __str__(self):
        return self.organization_name


@register_snippet
class Testimonial(DraftStateMixin, RevisionMixin, models.Model):
    quote = models.TextField(max_length=2000)
    person = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    related_service = models.ForeignKey(
        ServicePage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="testimonials",
    )
    related_case_study = models.ForeignKey(
        CaseStudyPage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="testimonials",
    )
    active = models.BooleanField(default=True)

    panels = [
        FieldPanel("quote"),
        FieldPanel("person"),
        FieldPanel("role"),
        FieldPanel("organization"),
        FieldPanel("related_service"),
        FieldPanel("related_case_study"),
        FieldPanel("active"),
        PublishingPanel(),
    ]

    def __str__(self):
        return f"{self.person} — {self.organization}".strip(" —")


@register_setting
class SiteSettings(BaseSiteSetting):
    public_contact_email = models.EmailField(blank=True)
    public_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    default_cta_label = models.CharField(max_length=100, blank=True)
    default_cta_url = models.URLField(max_length=500, blank=True)
    social_links = StreamField(
        [("social_link", SocialLinkBlock())],
        blank=True,
        use_json_field=True,
    )
    default_social_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [
        FieldPanel("public_contact_email"),
        FieldPanel("public_phone"),
        FieldPanel("address"),
        FieldPanel("default_cta_label"),
        FieldPanel("default_cta_url"),
        FieldPanel("social_links"),
        FieldPanel("default_social_image"),
    ]
