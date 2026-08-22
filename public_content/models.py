from datetime import time

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail import blocks as wagtail_blocks
from wagtail.admin.panels import FieldPanel, InlinePanel, PublishingPanel
from wagtail.api import APIField
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.models import DraftStateMixin, Orderable, Page, RevisionMixin
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from .api_fields import (
    ActivePricingItemsField,
    ControlledImageRenditionField,
    OrderedCollaboratorsField,
    OrderedRelatedPagesField,
    OrderedTestimonialsField,
    PublicPageListField,
    PublicUpdateListField,
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
        "public_content.ContactPage",
        "public_content.PricingPage",
        "public_content.UpdatesIndexPage",
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
    selected_work_enabled = models.BooleanField(
        default=True,
        help_text="Show the selected work section on the public homepage.",
    )
    selected_work_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="Selected work",
    )
    selected_work_heading = models.CharField(
        max_length=255,
        default="Turning research into meaningful stories",
    )
    selected_work_cta_label = models.CharField(
        max_length=100,
        blank=True,
        default="View all work",
    )
    selected_work_cta_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://labiomedia.com/work",
    )
    services_enabled = models.BooleanField(
        default=True,
        help_text="Show the services section on the public homepage.",
    )
    services_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="What we do",
    )
    services_heading = models.CharField(
        max_length=255,
        default="Communication solutions for research and innovation.",
    )
    services_cta_label = models.CharField(
        max_length=100,
        blank=True,
        default="See all services",
    )
    services_cta_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://labiomedia.com/services",
    )
    collaborators_enabled = models.BooleanField(
        default=True,
        help_text="Show the collaborators section on the public homepage.",
    )
    collaborators_heading = models.CharField(
        max_length=255,
        default="Trusted by research groups and organisations",
    )
    testimonials_enabled = models.BooleanField(
        default=True,
        help_text="Show selected testimonials on the public homepage.",
    )
    testimonials_heading = models.CharField(
        max_length=255,
        default="Client perspectives",
    )

    about_enabled = models.BooleanField(
        default=True,
        help_text="Show the about section on the public homepage.",
    )
    about_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="About LaBio Media",
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
    about_cta_label = models.CharField(
        max_length=100,
        blank=True,
        default="More about LaBio Media",
    )
    about_cta_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://labiomedia.com/about",
    )
    contact_enabled = models.BooleanField(
        default=True,
        help_text="Show the contact section on the public homepage.",
    )
    contact_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="Contact",
    )
    contact_heading = models.CharField(max_length=255)
    contact_copy = models.TextField(max_length=1000)
    contact_cta_label = models.CharField(max_length=100)
    contact_cta_url = models.URLField(max_length=500)
    updates_enabled = models.BooleanField(
        default=True,
        help_text="Show the latest published updates on the public homepage.",
    )
    updates_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="From LaBio",
    )
    updates_heading = models.CharField(
        max_length=255,
        default="A few notes, ideas and milestones.",
    )
    updates_item_count = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text="Number of latest published updates to show (1–6).",
    )
    updates_cta_label = models.CharField(
        max_length=100,
        blank=True,
        default="View all updates",
    )
    updates_cta_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://labiomedia.com/updates",
    )

    @property
    def latest_updates(self):
        if not self.updates_enabled:
            return []
        updates_index = (
            UpdatesIndexPage.objects.child_of(self).live().public().first()
        )
        if updates_index is None:
            return []
        return list(
            Page.objects.child_of(updates_index)
            .live()
            .public()
            .type(ArticlePage, EventPage)
            .order_by("-first_published_at", "-pk")
            .specific()[: self.updates_item_count]
        )

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
        FieldPanel("selected_work_enabled"),
        FieldPanel("selected_work_eyebrow"),
        FieldPanel("selected_work_heading"),
        FieldPanel("selected_work_cta_label"),
        FieldPanel("selected_work_cta_url"),
        InlinePanel("selected_case_studies", label="Selected case study"),
        FieldPanel("services_enabled"),
        FieldPanel("services_eyebrow"),
        FieldPanel("services_heading"),
        FieldPanel("services_cta_label"),
        FieldPanel("services_cta_url"),
        InlinePanel("featured_services", label="Featured service"),
        FieldPanel("collaborators_enabled"),
        FieldPanel("collaborators_heading"),
        InlinePanel(
            "homepage_collaborators",
            label="Collaborator",
            help_text="Choose and drag collaborators into public display order.",
        ),
        FieldPanel("testimonials_enabled"),
        FieldPanel("testimonials_heading"),
        InlinePanel(
            "homepage_testimonials",
            label="Testimonial",
            help_text="Choose and drag testimonials into public display order.",
        ),
        FieldPanel("about_enabled"),
        FieldPanel("about_eyebrow"),
        FieldPanel("about_heading"),
        FieldPanel("about_copy"),
        FieldPanel("about_image"),
        FieldPanel("about_image_alt"),
        FieldPanel("about_cta_label"),
        FieldPanel("about_cta_url"),
        FieldPanel("contact_enabled"),
        FieldPanel("contact_eyebrow"),
        FieldPanel("contact_heading"),
        FieldPanel("contact_copy"),
        FieldPanel("contact_cta_label"),
        FieldPanel("contact_cta_url"),
        FieldPanel("updates_enabled"),
        FieldPanel("updates_eyebrow"),
        FieldPanel("updates_heading"),
        FieldPanel("updates_item_count"),
        FieldPanel("updates_cta_label"),
        FieldPanel("updates_cta_url"),
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
        APIField("selected_work_enabled"),
        APIField("selected_work_eyebrow"),
        APIField("selected_work_heading"),
        APIField("selected_work_cta_label"),
        APIField("selected_work_cta_url"),
        APIField(
            "selected_work",
            serializer=OrderedRelatedPagesField(
                page_attribute="case_study",
                source="selected_case_studies",
            ),
        ),
        APIField("services_enabled"),
        APIField("services_eyebrow"),
        APIField("services_heading"),
        APIField("services_cta_label"),
        APIField("services_cta_url"),
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
        APIField("testimonials_enabled"),
        APIField("testimonials_heading"),
        APIField(
            "testimonials",
            serializer=OrderedTestimonialsField(
                source="homepage_testimonials",
            ),
        ),
        APIField("about_enabled"),
        APIField("about_eyebrow"),
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
        APIField("about_cta_label"),
        APIField("about_cta_url"),
        APIField("contact_enabled"),
        APIField("contact_eyebrow"),
        APIField("contact_heading"),
        APIField("contact_copy"),
        APIField("contact_cta_label"),
        APIField("contact_cta_url"),
        APIField("updates_enabled"),
        APIField("updates_eyebrow"),
        APIField("updates_heading"),
        APIField("updates_item_count"),
        APIField("updates_cta_label"),
        APIField("updates_cta_url"),
        APIField(
            "latest_updates",
            serializer=PublicUpdateListField(),
        ),
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


class UpdatesIndexPage(HeadlessPageMixin, PublicSEOMixin, Page):
    max_count = 1
    parent_page_types = ["public_content.HomePage"]
    subpage_types = [
        "public_content.ArticlePage",
        "public_content.EventPage",
    ]

    @property
    def published_articles(self):
        return (
            ArticlePage.objects.child_of(self)
            .live()
            .public()
            .order_by("-publication_date", "-first_published_at", "-pk")
        )

    @property
    def upcoming_events(self):
        today = timezone.localdate()
        events = [
            event
            for event in EventPage.objects.child_of(self).live().public()
            if (event.end_date or event.start_date) >= today
        ]
        return sorted(
            events,
            key=lambda event: (
                event.start_date,
                event.start_time or time.min,
                event.pk,
            ),
        )

    @property
    def past_events(self):
        today = timezone.localdate()
        events = [
            event
            for event in EventPage.objects.child_of(self).live().public()
            if (event.end_date or event.start_date) < today
        ]
        return sorted(
            events,
            key=lambda event: (
                event.start_date,
                event.start_time or time.min,
                event.pk,
            ),
            reverse=True,
        )

    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField(
            "articles",
            serializer=PublicUpdateListField(source="published_articles"),
        ),
        APIField(
            "upcoming_events",
            serializer=PublicUpdateListField(),
        ),
        APIField(
            "past_events",
            serializer=PublicUpdateListField(),
        ),
    ]


class ArticlePage(HeadlessPageMixin, PublicSEOMixin, Page):
    class ArticleType(models.TextChoices):
        INSIGHT = "insight", "Insight"
        MILESTONE = "milestone", "Milestone"
        UPDATE = "update", "Update"

    parent_page_types = ["public_content.UpdatesIndexPage"]
    subpage_types = []

    article_type = models.CharField(
        max_length=20,
        choices=ArticleType.choices,
        default=ArticleType.UPDATE,
    )
    summary = models.TextField(max_length=1000)
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    featured_image_alt = models.CharField(max_length=255)
    publication_date = models.DateField()
    featured = models.BooleanField(default=False)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("article_type"),
        FieldPanel("summary"),
        FieldPanel("featured_image"),
        FieldPanel("featured_image_alt"),
        FieldPanel("publication_date"),
        FieldPanel("featured"),
        FieldPanel("body"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    search_fields = Page.search_fields + [
        index.SearchField("summary"),
        index.SearchField("body"),
    ]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("article_type"),
        APIField("summary"),
        APIField(
            "featured_image",
            serializer=ControlledImageRenditionField(
                "featured_image",
                "featured_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("publication_date"),
        APIField("featured"),
        APIField("body"),
    ]


class EventPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.UpdatesIndexPage"]
    subpage_types = []

    summary = models.TextField(max_length=1000)
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    featured_image_alt = models.CharField(max_length=255)
    start_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    registration_url = models.URLField(max_length=500, blank=True)
    featured = models.BooleanField(default=False)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    def clean(self):
        super().clean()
        effective_end_date = self.end_date or self.start_date
        if effective_end_date < self.start_date:
            raise ValidationError(
                {"end_date": "End date cannot be before the start date."}
            )
        if (
            self.start_time
            and self.end_time
            and effective_end_date == self.start_date
            and self.end_time <= self.start_time
        ):
            raise ValidationError(
                {"end_time": "End time must be after the start time."}
            )

    content_panels = Page.content_panels + [
        FieldPanel("summary"),
        FieldPanel("featured_image"),
        FieldPanel("featured_image_alt"),
        FieldPanel("start_date"),
        FieldPanel("start_time"),
        FieldPanel("end_date"),
        FieldPanel("end_time"),
        FieldPanel("location"),
        FieldPanel("registration_url"),
        FieldPanel("featured"),
        FieldPanel("body"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    search_fields = Page.search_fields + [
        index.SearchField("summary"),
        index.SearchField("body"),
        index.SearchField("location"),
    ]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("summary"),
        APIField(
            "featured_image",
            serializer=ControlledImageRenditionField(
                "featured_image",
                "featured_image_alt",
                "fill-1920x1080",
            ),
        ),
        APIField("start_date"),
        APIField("start_time"),
        APIField("end_date"),
        APIField("end_time"),
        APIField("location"),
        APIField("registration_url"),
        APIField("featured"),
        APIField("body"),
    ]


class CaseStudyPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.PortfolioIndexPage"]
    subpage_types = []

    client_display_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=150)
    summary = models.TextField(max_length=1000, blank=True)
    project_year = models.CharField(
        max_length=20,
        blank=True,
        help_text='Editorial year or range, such as "2025" or "2024–2025".',
    )
    challenge = models.TextField(max_length=4000, blank=True)
    approach = models.TextField(max_length=4000, blank=True)
    outcome = models.TextField(max_length=4000, blank=True)
    deliverables = StreamField(
        [
            (
                "deliverable",
                wagtail_blocks.CharBlock(
                    max_length=255,
                    label="Deliverable",
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )
    project_url = models.URLField(max_length=500, blank=True)
    cta_label = models.CharField(max_length=100, blank=True)
    cta_url = models.URLField(max_length=500, blank=True)
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
        FieldPanel("project_year"),
        FieldPanel("challenge"),
        FieldPanel("approach"),
        FieldPanel("deliverables"),
        FieldPanel("outcome"),
        FieldPanel("project_url"),
        FieldPanel("cta_label"),
        FieldPanel("cta_url"),
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
    search_fields = Page.search_fields + [
        index.SearchField("client_display_name"),
        index.SearchField("summary"),
        index.SearchField("challenge"),
        index.SearchField("approach"),
        index.SearchField("outcome"),
        index.SearchField("body"),
    ]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("client_display_name"),
        APIField("category"),
        APIField("summary"),
        APIField("project_year"),
        APIField("challenge"),
        APIField("approach"),
        APIField("deliverables"),
        APIField("outcome"),
        APIField("project_url"),
        APIField("cta_label"),
        APIField("cta_url"),
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
    page_eyebrow = models.CharField(
        max_length=150,
        blank=True,
        default="About LaBio Media",
    )
    values_label = models.CharField(
        max_length=150,
        blank=True,
        default="Values",
    )
    process_label = models.CharField(
        max_length=150,
        blank=True,
        default="How we work",
    )
    testimonials_enabled = models.BooleanField(
        default=True,
        help_text="Show selected testimonials on the public About page.",
    )
    testimonials_heading = models.CharField(
        max_length=255,
        default="Client perspectives",
    )

    @property
    def public_testimonial_relations(self):
        if not self.testimonials_enabled:
            return self.about_testimonials.none()
        return self.about_testimonials

    content_panels = Page.content_panels + [
        FieldPanel("hero_image"),
        FieldPanel("hero_image_alt"),
        FieldPanel("intro"),
        FieldPanel("body"),
        FieldPanel("values"),
        FieldPanel("process"),
        FieldPanel("page_eyebrow"),
        FieldPanel("values_label"),
        FieldPanel("process_label"),
        FieldPanel("testimonials_enabled"),
        FieldPanel("testimonials_heading"),
        InlinePanel(
            "about_testimonials",
            label="Testimonial",
            help_text="Choose and drag testimonials into public display order.",
        ),
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
        APIField("page_eyebrow"),
        APIField("values_label"),
        APIField("process_label"),
        APIField("testimonials_enabled"),
        APIField("testimonials_heading"),
        APIField(
            "testimonials",
            serializer=OrderedTestimonialsField(
                source="public_testimonial_relations"
            ),
        ),
    ]


class StandardPage(HeadlessPageMixin, PublicSEOMixin, Page):
    parent_page_types = ["public_content.HomePage", "public_content.StandardPage"]
    subpage_types = ["public_content.StandardPage"]

    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("body")]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [APIField("body")]


class ContactPage(HeadlessPageMixin, PublicSEOMixin, Page):
    max_count = 1
    parent_page_types = ["public_content.HomePage"]
    subpage_types = []

    eyebrow = models.CharField(max_length=150, default="Contact")
    intro = models.TextField(max_length=1500)
    body = StreamField(PublicBodyBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("eyebrow"),
        FieldPanel("intro"),
        FieldPanel("body"),
    ]
    promote_panels = Page.promote_panels + [FieldPanel("social_image")]
    api_fields = PublicSEOMixin.seo_api_fields + [
        APIField("eyebrow"),
        APIField("intro"),
        APIField("body"),
    ]


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
    class PricingMode(models.TextChoices):
        STARTING_FROM = "starting_from", "Starting from"
        FIXED = "fixed", "Fixed price"
        CUSTOM = "custom", "Custom / contact us"

    page = ParentalKey(
        PricingPage,
        related_name="pricing_items",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    pricing_mode = models.CharField(
        max_length=20,
        choices=PricingMode.choices,
        default=PricingMode.STARTING_FROM,
    )
    currency = models.CharField(
        max_length=10,
        blank=True,
        default="€",
        help_text='Currency symbol or code, such as "€" or "EUR".',
    )
    price_label = models.CharField(
        max_length=100,
        help_text=(
            'Enter the amount, such as "1,500", or custom wording such as '
            '"Let’s talk". Existing formatted labels remain supported.'
        ),
    )
    description = models.TextField(max_length=1000)
    ideal_for = models.TextField(
        max_length=1500,
        blank=True,
        help_text="Who this offer is designed for.",
    )
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
    context = models.TextField(
        max_length=2000,
        blank=True,
        help_text="Optional scope, exclusions, or other pricing context.",
    )
    cta_label = models.CharField(max_length=100)
    cta_url = models.URLField(
        max_length=500,
        help_text="Use the full public destination URL.",
    )
    featured = models.BooleanField(
        default=False,
        help_text="Give this offer subtle emphasis on the public pricing page.",
    )
    active = models.BooleanField(
        default=True,
        help_text="Inactive items stay in the CMS but are hidden publicly.",
    )
    related_services = StreamField(
        [
            (
                "service",
                wagtail_blocks.PageChooserBlock(
                    target_model="public_content.ServicePage",
                    label="Service",
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )
    related_case_studies = StreamField(
        [
            (
                "case_study",
                wagtail_blocks.PageChooserBlock(
                    target_model="public_content.CaseStudyPage",
                    label="Case study",
                ),
            )
        ],
        blank=True,
        use_json_field=True,
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("pricing_mode"),
        FieldPanel("currency"),
        FieldPanel("price_label"),
        FieldPanel("description"),
        FieldPanel("ideal_for"),
        FieldPanel("features"),
        FieldPanel("context"),
        FieldPanel("cta_label"),
        FieldPanel("cta_url"),
        FieldPanel("featured"),
        FieldPanel("active"),
        FieldPanel("related_services"),
        FieldPanel("related_case_studies"),
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


class HomePageTestimonial(Orderable):
    page = ParentalKey(
        HomePage,
        related_name="homepage_testimonials",
        on_delete=models.CASCADE,
    )
    testimonial = models.ForeignKey(
        "public_content.Testimonial",
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [FieldPanel("testimonial")]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "testimonial"],
                name="unique_homepage_testimonial",
            )
        ]


class AboutPageTestimonial(Orderable):
    page = ParentalKey(
        AboutPage,
        related_name="about_testimonials",
        on_delete=models.CASCADE,
    )
    testimonial = models.ForeignKey(
        "public_content.Testimonial",
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [FieldPanel("testimonial")]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "testimonial"],
                name="unique_aboutpage_testimonial",
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
    legal_business_name = models.CharField(max_length=255, blank=True)
    business_id = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=150, blank=True)
    country = models.CharField(max_length=150, blank=True)
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
        FieldPanel("legal_business_name"),
        FieldPanel("business_id"),
        FieldPanel("address"),
        FieldPanel("city"),
        FieldPanel("country"),
        FieldPanel("public_contact_email"),
        FieldPanel("public_phone"),
        FieldPanel("default_cta_label"),
        FieldPanel("default_cta_url"),
        FieldPanel("social_links"),
        FieldPanel("default_social_image"),
    ]
