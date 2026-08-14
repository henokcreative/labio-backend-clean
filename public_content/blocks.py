from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.rich_text import expand_db_html

from .api_fields import get_rendition_data


RICH_TEXT_FEATURES = ["bold", "italic", "link", "ol", "ul"]


class PublicRichTextBlock(blocks.RichTextBlock):
    def __init__(self, **kwargs):
        kwargs.setdefault("features", RICH_TEXT_FEATURES)
        super().__init__(**kwargs)

    def get_api_representation(self, value, context=None):
        return expand_db_html(value.source)


class HeadingBlock(blocks.StructBlock):
    text = blocks.CharBlock(max_length=255)
    level = blocks.ChoiceBlock(
        choices=[("h2", "Heading 2"), ("h3", "Heading 3")],
        default="h2",
    )

    class Meta:
        icon = "title"
        label = "Heading"


class PublicImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=True)
    alt_text = blocks.CharBlock(required=True, max_length=255)
    caption = blocks.CharBlock(required=False, max_length=500)

    def get_api_representation(self, value, context=None):
        representation = get_rendition_data(
            value.get("image"),
            "max-1600x1600",
            value.get("alt_text", ""),
        )
        if representation is not None and value.get("caption"):
            representation["caption"] = value["caption"]
        return representation

    class Meta:
        icon = "image"
        label = "Image"


class GalleryImageBlock(PublicImageBlock):
    class Meta:
        icon = "image"
        label = "Gallery image"


class QuoteBlock(blocks.StructBlock):
    quote = blocks.TextBlock(max_length=1000)
    attribution = blocks.CharBlock(required=False, max_length=255)

    class Meta:
        icon = "openquote"
        label = "Quote"


class PublicEmbedBlock(EmbedBlock):
    def get_api_representation(self, value, context=None):
        return value.url if value else None


class CTABlock(blocks.StructBlock):
    label = blocks.CharBlock(max_length=100)
    url = blocks.URLBlock()

    class Meta:
        icon = "link"
        label = "Call to action"


class CapabilityBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=150)
    description = blocks.TextBlock(required=False, max_length=500)

    class Meta:
        icon = "list-ul"
        label = "Capability"


class ProcessStepBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=150)
    description = blocks.TextBlock(max_length=1000)

    class Meta:
        icon = "list-ol"
        label = "Process step"


class ValueBlock(blocks.StructBlock):
    title = blocks.CharBlock(max_length=150)
    description = blocks.TextBlock(max_length=1000)

    class Meta:
        icon = "pick"
        label = "Value"


class SocialLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock(max_length=100)
    url = blocks.URLBlock()

    class Meta:
        icon = "link"
        label = "Social link"


class PublicBodyBlock(blocks.StreamBlock):
    heading = HeadingBlock()
    rich_text = PublicRichTextBlock()
    image = PublicImageBlock()
    quote = QuoteBlock()
    embed = PublicEmbedBlock()
    cta = CTABlock()

    class Meta:
        icon = "doc-full"
        label = "Content"
