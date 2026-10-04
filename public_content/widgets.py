from django import forms


class IncludedFeaturesTextarea(forms.Textarea):
    """A line-based editor for the existing pricing feature StreamField."""

    def __init__(self, attrs=None):
        super().__init__({"rows": 9, **(attrs or {})})

    def format_value(self, value):
        if not value:
            return ""
        return "\n".join(str(block.value) for block in value if block.block_type == "feature")

    def value_from_datadict(self, data, files, name):
        # Keep Wagtail's original block validation, storage and revision format.
        from .models import PricingItem

        text = super().value_from_datadict(data, files, name) or ""
        block = PricingItem._meta.get_field("features").stream_block
        return block.to_python([
            {"type": "feature", "value": line.strip()}
            for line in text.splitlines() if line.strip()
        ])
