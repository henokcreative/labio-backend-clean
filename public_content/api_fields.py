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


class ActivePricingItemsField(Field):
    def __init__(self, **kwargs):
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        items = value.filter(active=True).order_by("sort_order", "pk")
        return [
            {
                "id": item.pk,
                "title": item.title,
                "price_label": item.price_label,
                "description": item.description,
                "features": [
                    str(block.value)
                    for block in item.features
                    if block.block_type == "feature"
                ],
                "cta_label": item.cta_label,
                "cta_url": item.cta_url,
            }
            for item in items
        ]
