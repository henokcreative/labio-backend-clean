import json
from importlib import import_module

from django.test import SimpleTestCase

from .blocks import NarrativeRichTextBlock


legacy = import_module("public_content.migrations.0019_case_study_narrative")
repair = import_module("public_content.migrations.0020_repair_narrative_line_breaks")


class NarrativeLineBreakTests(SimpleTestCase):
    def test_reproduces_0019_error_and_repaired_block_loads_in_draftail(self):
        blocks = legacy.legacy_narrative({"challenge": "First line\nSecond line"})
        block = NarrativeRichTextBlock()
        with self.assertRaisesRegex(AssertionError, "Unmatched tags: expected br, got p"):
            block.get_form_state(block.to_python(blocks[0]["value"]))
        fixed, changed = repair.repair_narrative(blocks)
        self.assertTrue(changed)
        self.assertEqual(fixed[0]["id"], blocks[0]["id"])
        self.assertEqual(fixed[0]["value"], "<h3>Challenge</h3><p>First line<br/>Second line</p>")
        block.get_form_state(block.to_python(fixed[0]["value"]))
        state = json.loads(block.field.widget.converter.from_database_format(fixed[0]["value"]))
        self.assertEqual(state["blocks"][1]["text"], "First line\nSecond line")

    def test_migrated_paragraphs_escaping_and_empty_fields_load(self):
        cases = [
            {}, {"challenge": ""}, {"challenge": "\n"},
            {"challenge": "One\nTwo\n\nThree"},
            {"approach": "One\r\nTwo\r\n\r\nThree"},
            {"outcome": "Leading\n\n\nTrailing\n"},
            {"challenge": '<p>Literal HTML</p> & <br> "quotes"\n<script>literal</script>'},
            {"deliverables": [{"type": "deliverable", "value": "A < B & C\nD"}]},
        ]
        block = NarrativeRichTextBlock()
        for content in cases:
            with self.subTest(content=content):
                original = legacy.legacy_narrative(content)
                fixed, _ = repair.repair_narrative(original)
                for before, after in zip(original, fixed):
                    self.assertEqual(after["value"], before["value"].replace("<br>", "<br/>"))
                    block.get_form_state(block.to_python(after["value"]))
                self.assertEqual(repair.repair_narrative(fixed), (fixed, False))

    def test_only_actual_open_break_tags_change(self):
        html = ('<p>Escaped &lt;br&gt; <a href="https://example.com/?q=<br>">Link</a>'
                '\nline<br>next<br/>last</p>')
        original = [{"type": "rich_text", "id": "keep", "value": html}]
        fixed, changed = repair.repair_narrative(original)
        self.assertTrue(changed)
        self.assertEqual(fixed[0]["value"], html.replace("line<br>", "line<br/>"))
        self.assertEqual(original[0]["value"], html)

    def test_editor_content_block_ids_and_valid_markup_remain_unchanged(self):
        blocks = [
            {"type": "rich_text", "id": "first", "value": '<h2>Edited heading</h2><p>New text<br>Second line</p>'},
            {"type": "rich_text", "id": "second", "value": '<ul><li>Brand<ul><li><strong>Logo</strong></li></ul></li></ul><p><a href="/work/">Work</a><br/></p>'},
        ]
        fixed, changed = repair.repair_narrative(blocks)
        self.assertTrue(changed)
        self.assertEqual(fixed[0], {**blocks[0], "value": blocks[0]["value"].replace("<br>", "<br/>")})
        self.assertEqual(fixed[1], blocks[1])
        for item in fixed:
            block = NarrativeRichTextBlock()
            block.get_form_state(block.to_python(item["value"]))
        self.assertEqual(repair.repair_narrative(fixed), (fixed, False))

    def test_already_loadable_paired_break_is_unchanged(self):
        blocks = [{"type": "rich_text", "id": "valid", "value": "<p>One<br></br>Two</p>"}]
        self.assertEqual(repair.repair_narrative(blocks), (blocks, False))
