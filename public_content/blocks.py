from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
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


class ShowcaseImageBlock(PublicImageBlock):
    class Meta:
        icon = "image"
        label = "Showcase image"


class PhotoSliderBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    images = blocks.ListBlock(
        ShowcaseImageBlock(),
        min_num=2,
        max_num=20,
        label="Slides",
    )

    class Meta:
        icon = "image"
        label = "Photo slider"


class MasonryGalleryBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    images = blocks.ListBlock(
        ShowcaseImageBlock(),
        min_num=2,
        max_num=30,
        label="Images",
    )

    class Meta:
        icon = "image"
        label = "Masonry gallery"


class ImageGridBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    columns = blocks.ChoiceBlock(
        choices=[("2", "Two columns"), ("3", "Three columns")],
        default="3",
    )
    images = blocks.ListBlock(
        ShowcaseImageBlock(),
        min_num=1,
        max_num=24,
        label="Images",
    )

    class Meta:
        icon = "grip"
        label = "Image grid"


class ImagePairBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    first_image = ShowcaseImageBlock(label="First image")
    second_image = ShowcaseImageBlock(label="Second image")

    class Meta:
        icon = "image"
        label = "Image pair"


class VideoShowcaseBlock(blocks.StructBlock):
    ALLOWED_HOSTS = {
        "youtu.be",
        "youtube.com",
        "www.youtube.com",
        "vimeo.com",
        "www.vimeo.com",
    }

    heading = blocks.CharBlock(required=False, max_length=255)
    url = blocks.URLBlock(label="YouTube or Vimeo URL")
    caption = blocks.CharBlock(required=False, max_length=500)

    def clean(self, value):
        cleaned = super().clean(value)
        parsed = urlparse(cleaned["url"])
        hostname = (parsed.hostname or "").lower()
        has_video_id = (
            (hostname == "youtu.be" and bool(parsed.path.strip("/")))
            or (
                hostname in {"youtube.com", "www.youtube.com"}
                and bool(parse_qs(parsed.query).get("v", [""])[0])
            )
            or (
                hostname in {"vimeo.com", "www.vimeo.com"}
                and bool(parsed.path.strip("/").split("/")[0])
            )
        )
        if hostname not in self.ALLOWED_HOSTS or not has_video_id:
            raise blocks.StructBlockValidationError(
                block_errors={
                    "url": ValidationError(
                        "Use a public YouTube or Vimeo URL."
                    )
                }
            )
        return cleaned

    class Meta:
        icon = "media"
        label = "Video embed"


class WebsitePreviewItemBlock(blocks.StructBlock):
    image = ImageChooserBlock(required=True)
    alt_text = blocks.CharBlock(required=True, max_length=255)
    label = blocks.CharBlock(max_length=150)
    url = blocks.URLBlock(required=False, label="Optional destination URL")
    caption = blocks.CharBlock(required=False, max_length=500)

    def get_api_representation(self, value, context=None):
        return {
            "image": get_rendition_data(
                value.get("image"),
                "max-1400x1000",
                value.get("alt_text", ""),
            ),
            "label": value.get("label", ""),
            "url": value.get("url", ""),
            "caption": value.get("caption", ""),
        }

    class Meta:
        icon = "site"
        label = "Website preview"


class WebsitePreviewGridBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    items = blocks.ListBlock(
        WebsitePreviewItemBlock(),
        min_num=1,
        max_num=12,
        label="Website previews",
    )

    class Meta:
        icon = "site"
        label = "Website preview grid"


class WideImageBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=255)
    image = ImageChooserBlock(required=True)
    alt_text = blocks.CharBlock(required=True, max_length=255)
    caption = blocks.CharBlock(required=False, max_length=500)

    def get_api_representation(self, value, context=None):
        return {
            "heading": value.get("heading", ""),
            "image": get_rendition_data(
                value.get("image"),
                "max-2000x1400",
                value.get("alt_text", ""),
            ),
            "caption": value.get("caption", ""),
        }

    class Meta:
        icon = "image"
        label = "Wide image"


class CaseStudyShowcaseBlock(blocks.StreamBlock):
    photo_slider = PhotoSliderBlock()
    masonry_gallery = MasonryGalleryBlock()
    image_grid = ImageGridBlock()
    image_pair = ImagePairBlock()
    video = VideoShowcaseBlock()
    website_preview_grid = WebsitePreviewGridBlock()
    wide_image = WideImageBlock()

    class Meta:
        icon = "image"
        label = "Visual showcase"


class UpdateShowcaseBlock(blocks.StreamBlock):
    masonry_gallery = MasonryGalleryBlock()
    image_grid = ImageGridBlock()
    image_pair = ImagePairBlock()
    video = VideoShowcaseBlock()
    wide_image = WideImageBlock()

    class Meta:
        icon = "image"
        label = "Editorial media"


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


class NavigationLinkBlock(blocks.StructBlock):
    label = blocks.CharBlock(max_length=100)
    page = blocks.PageChooserBlock(required=False)
    url = blocks.URLBlock(required=False)
    enabled = blocks.BooleanBlock(required=False, default=True)
    external = blocks.BooleanBlock(required=False, default=False)

    def clean(self, value):
        cleaned = super().clean(value)
        has_page = bool(cleaned.get("page"))
        has_url = bool(cleaned.get("url"))
        if has_page == has_url:
            message = "Choose an internal page or enter one external URL."
            raise blocks.StructBlockValidationError(
                non_block_errors=[message],
            )
        return cleaned

    class Meta:
        icon = "link"
        label = "Navigation link"


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
