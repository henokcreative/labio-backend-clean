from rest_framework.fields import Field
from wagtail.images.models import SourceImageIOError
from wagtail.models import Page


def get_rendition_data(image, filter_spec, alt_text=""):
    if image is None:
        return None
    try:
        rendition = image.get_rendition(filter_spec)
    except SourceImageIOError:
        return None
    return {
        "url": rendition.url,
        "width": rendition.width,
        "height": rendition.height,
        "alt": alt_text or image.title,
    }


def public_page_summary(page):
    page = page.specific
    summary = {
        "id": page.id,
        "title": page.title,
        "slug": page.slug,
    }
    for field_name in ("summary", "category"):
        value = getattr(page, field_name, "")
        if value:
            summary[field_name] = value
    return summary


def only_public_pages(pages):
    pages = list(pages)
    public_ids = set(
        Page.objects.live()
        .public()
        .filter(pk__in=[page.pk for page in pages])
        .values_list("pk", flat=True)
    )
    return [page for page in pages if page.pk in public_ids]


class ControlledImageRenditionField(Field):
    def __init__(self, image_source, alt_source=None, filter_spec="max-1600x1600", **kwargs):
        self.image_source = image_source
        self.alt_source = alt_source
        self.filter_spec = filter_spec
        kwargs.setdefault("source", "*")
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, instance):
        image = getattr(instance, self.image_source, None)
        alt_text = (
            getattr(instance, self.alt_source, "")
            if self.alt_source
            else ""
        )
        return get_rendition_data(image, self.filter_spec, alt_text)


class PublicPageListField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        pages = value.all() if hasattr(value, "all") else value
        return [public_page_summary(page) for page in only_public_pages(pages)]


def public_update_summary(page):
    page = page.specific
    summary = {
        "id": page.id,
        "title": page.title,
        "slug": page.slug,
        "summary": page.summary,
        "featured": page.featured,
        "featured_image": get_rendition_data(
            page.featured_image,
            "fill-1200x675",
            page.featured_image_alt,
        ),
    }
    if hasattr(page, "article_type"):
        summary.update(
            {
                "kind": "article",
                "article_type": page.article_type,
                "article_type_label": page.get_article_type_display(),
                "publication_date": page.publication_date.isoformat(),
            }
        )
    else:
        summary.update(
            {
                "kind": "event",
                "start_date": page.start_date.isoformat(),
                "start_time": (
                    page.start_time.isoformat() if page.start_time else None
                ),
                "end_date": (
                    page.end_date.isoformat() if page.end_date else None
                ),
                "end_time": page.end_time.isoformat() if page.end_time else None,
                "location": page.location,
                "registration_url": page.registration_url,
            }
        )
    return summary


class PublicUpdateListField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        return [public_update_summary(page) for page in only_public_pages(value)]


class OrderedRelatedPagesField(Field):
    def __init__(self, page_attribute, **kwargs):
        self.page_attribute = page_attribute
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        relations = list(value.all())
        pages = [getattr(relation, self.page_attribute) for relation in relations]
        public_ids = {page.pk for page in only_public_pages(pages)}
        return [
            public_page_summary(page)
            for page in pages
            if page.pk in public_ids
        ]


class OrderedRelatedCaseStudiesField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        relations = list(
            value.select_related(
                "case_study",
                "case_study__hero_image",
            ).order_by("sort_order", "pk")
        )
        pages = [relation.case_study for relation in relations]
        public_ids = {page.pk for page in only_public_pages(pages)}
        return [
            {
                "id": page.pk,
                "title": page.title,
                "slug": page.slug,
                "summary": page.summary,
                "category": page.category,
                "hero_image": get_rendition_data(
                    page.hero_image,
                    "fill-1200x800",
                    page.hero_image_alt,
                ),
            }
            for page in pages
            if page.pk in public_ids
        ]


class OrderedCollaboratorsField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        relations = value.select_related("collaborator").order_by(
            "sort_order",
            "pk",
        )
        collaborators = []
        for relation in relations:
            collaborator = relation.collaborator
            if not collaborator.live or not collaborator.active:
                continue
            collaborators.append(
                {
                    "id": collaborator.pk,
                    "organization_name": collaborator.organization_name,
                    "logo": get_rendition_data(
                        collaborator.logo,
                        "max-600x300",
                        collaborator.logo_alt,
                    ),
                    "url": collaborator.url,
                    "display_order": collaborator.display_order,
                    "visual_variant": collaborator.visual_variant,
                }
            )
        return collaborators


class OrderedTestimonialsField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    @staticmethod
    def public_relation(page):
        if page is None or not only_public_pages([page]):
            return None
        return public_page_summary(page)

    def to_representation(self, value):
        relations = value.select_related(
            "testimonial",
            "testimonial__portrait",
            "testimonial__related_service",
            "testimonial__related_case_study",
        ).order_by("sort_order", "pk")
        testimonials = []
        for relation in relations:
            testimonial = relation.testimonial
            if not testimonial.live or not testimonial.active:
                continue
            testimonials.append(
                {
                    "id": testimonial.pk,
                    "quote": testimonial.quote,
                    "person": testimonial.person,
                    "portrait": get_rendition_data(
                        testimonial.portrait,
                        "fill-144x144",
                        f"Portrait of {testimonial.person}",
                    ),
                    "role": testimonial.role,
                    "organization": testimonial.organization,
                    "related_service": self.public_relation(
                        testimonial.related_service
                    ),
                    "related_case_study": self.public_relation(
                        testimonial.related_case_study
                    ),
                }
            )
        return testimonials


class ActivePricingItemsField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        items = value.filter(active=True).order_by("sort_order", "pk")

        def related_pages(stream_value, block_type):
            pages = [
                block.value
                for block in stream_value
                if block.block_type == block_type and block.value is not None
            ]
            return [
                public_page_summary(page)
                for page in only_public_pages(pages)
            ]

        return [
            {
                "id": item.pk,
                "title": item.title,
                "pricing_mode": item.pricing_mode,
                "currency": item.currency,
                "price_label": item.price_label,
                "description": item.description,
                "ideal_for": item.ideal_for,
                "features": [
                    str(block.value)
                    for block in item.features
                    if block.block_type == "feature"
                ],
                "context": item.context,
                "cta_label": item.cta_label,
                "cta_url": item.cta_url,
                "featured": item.featured,
                "related_services": related_pages(
                    item.related_services,
                    "service",
                ),
                "related_case_studies": related_pages(
                    item.related_case_studies,
                    "case_study",
                ),
            }
            for item in items
        ]
