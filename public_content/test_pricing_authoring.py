from django.test import TestCase
from wagtail.blocks import StreamBlockValidationError

from .models import PricingItem, PricingPage
from .widgets import IncludedFeaturesTextarea


class PricingAuthoringTests(TestCase):
    def setUp(self):
        self.block = PricingItem._meta.get_field("features").stream_block
        self.widget = IncludedFeaturesTextarea()

    def test_existing_features_display_and_round_trip(self):
        value = self.block.to_python([
            {"type": "feature", "value": "Story planning", "id": "a"},
            {"type": "feature", "value": "Editing & subtitles", "id": "b"},
        ])
        text = self.widget.format_value(value)
        self.assertEqual(text, "Story planning\nEditing & subtitles")
        saved = self.widget.value_from_datadict({"features": text}, {}, "features")
        self.assertEqual([item.value for item in self.block.clean(saved)], [item.value for item in value])

    def test_blank_lines_and_empty_values(self):
        value = self.widget.value_from_datadict({"features": " Filming\r\n\nEditing "}, {}, "features")
        self.assertEqual([item.value for item in value], ["Filming", "Editing"])
        self.assertEqual(len(self.widget.value_from_datadict({}, {}, "features")), 0)
        self.assertEqual(self.widget.format_value(None), "")

    def test_existing_feature_length_validation(self):
        value = self.widget.value_from_datadict({"features": "x" * 256}, {}, "features")
        with self.assertRaises(StreamBlockValidationError):
            self.block.clean(value)

    def test_inline_editor_uses_textarea(self):
        form = PricingPage.get_edit_handler().get_form_class()
        field = form.formsets["pricing_items"].form.base_fields["features"]
        self.assertIsInstance(field.widget, IncludedFeaturesTextarea)
        value = field.widget.value_from_datadict({"features": "Planning\nProduction"}, {}, "features")
        self.assertEqual(len(field.clean(value)), 2)
