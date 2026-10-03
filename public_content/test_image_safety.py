from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from wagtail.images import get_image_model
from wagtail.images.fields import WagtailImageField

from .api_fields import get_rendition_data
from .tests import TEST_STORAGES


def upload():
    data = BytesIO()
    Image.new("RGBA", (32, 24), (255, 0, 0, 0)).save(data, "PNG")
    return SimpleUploadedFile("transparent.png", data.getvalue(), "image/png")


@override_settings(STORAGES=TEST_STORAGES)
class ImageSafetyTests(TestCase):
    def test_valid_upload(self):
        self.assertEqual(WagtailImageField().clean(upload()).image.get_size(), (32, 24))

    def test_pixel_limit_with_clear_error(self):
        field = WagtailImageField()
        value = field.clean(upload())
        with patch.object(value.image, "get_size", return_value=(5000, 4000)):
            with self.assertRaisesMessage(ValidationError, "too many pixels"):
                field.check_image_pixel_size(value)
        self.assertEqual(field.max_image_pixels, 16_000_000)

    def test_file_limit(self):
        value = upload()
        value.size = settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE + 1
        with self.assertRaisesMessage(ValidationError, "too big"):
            WagtailImageField().clean(value)

    def test_rendition_shape_cache_and_transparency(self):
        image = get_image_model().objects.create(title="Transparent", file=upload())
        result = get_rendition_data(image, "max-16x16")
        self.assertEqual(set(result), {"url", "width", "height", "alt"})
        self.assertEqual((result["width"], result["height"]), (16, 12))
        with patch.object(type(image), "create_rendition", side_effect=AssertionError("regenerated")):
            self.assertEqual(get_rendition_data(image, "max-16x16"), result)
        rendition = image.get_rendition("max-16x16")
        with rendition.file.open("rb") as source:
            decoded = Image.open(source).convert("RGBA")
            self.assertEqual(decoded.getpixel((0, 0))[3], 0)

    def test_legacy_oversized_uses_cached_only(self):
        image = get_image_model().objects.create(title="Legacy", file=upload())
        result = get_rendition_data(image, "max-16x16")
        image.width, image.height = 5000, 4000
        with patch.object(image, "get_rendition", side_effect=AssertionError("unsafe decode")):
            self.assertEqual(get_rendition_data(image, "max-16x16"), result)
            self.assertIsNone(get_rendition_data(image, "max-12x12"))

    def test_missing_image(self):
        self.assertIsNone(get_rendition_data(None, "max-16x16"))
