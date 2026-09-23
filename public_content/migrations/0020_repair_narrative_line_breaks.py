"""Repair 0019's HTML5 line breaks to Wagtail database-HTML syntax."""

import json
from html.parser import HTMLParser

from django.db import migrations
from wagtail.admin.rich_text.converters.contentstate import ContentstateConverter


class NarrativeLineBreakParser(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.line_offsets = [0]
        for index, character in enumerate(source):
            if character == "\n":
                self.line_offsets.append(index + 1)
        self.replacements = []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            # Only an actual opening tag, never escaped text or an attribute value.
            line, column = self.getpos()
            start = self.line_offsets[line - 1] + column
            original = self.get_starttag_text()
            self.replacements.append((start, start + len(original), original[:-1] + "/>"))

    def handle_startendtag(self, tag, attrs):
        # Already valid database HTML; leave it byte-for-byte unchanged.
        pass


def repair_narrative(blocks):
    repaired = []
    changed = False
    for block in blocks:
        html = block.get("value")
        if block.get("type") == "rich_text" and isinstance(html, str):
            replacements = NarrativeLineBreakParser(html).replacements
            if replacements:
                converter = ContentstateConverter(
                    features=["h2", "h3", "bold", "italic", "link", "ol", "ul"]
                )
                try:
                    converter.from_database_format(html)
                except AssertionError:
                    for start, end, replacement in reversed(replacements):
                        html = html[:start] + replacement + html[end:]
                    # Validate with Draftail, but avoid round-tripping all HTML:
                    # that could rewrite links, whitespace or editorial edits.
                    # Any remaining malformed markup aborts the atomic migration.
                    converter.from_database_format(html)
                    block = {**block, "value": html}
                    changed = True
                # Already-loadable markup (including paired <br></br>) is intact.
        repaired.append(block)
    return repaired, changed


def repair_narratives(apps, schema_editor):
    alias = schema_editor.connection.alias
    CaseStudy = apps.get_model("public_content", "CaseStudyPage")
    Revision = apps.get_model("wagtailcore", "Revision")
    ContentType = apps.get_model("contenttypes", "ContentType")

    for page in CaseStudy.objects.using(alias).all().iterator():
        blocks, changed = repair_narrative(page.narrative.get_prep_value())
        if changed:
            CaseStudy.objects.using(alias).filter(pk=page.pk).update(narrative=blocks)

    content_type = ContentType.objects.using(alias).filter(
        app_label="public_content", model="casestudypage"
    ).first()
    if content_type is None:
        return
    for revision in Revision.objects.using(alias).filter(content_type_id=content_type.pk).iterator():
        content = revision.content
        narrative = content.get("narrative")
        if narrative is None:
            continue
        blocks, changed = repair_narrative(
            json.loads(narrative) if isinstance(narrative, str) else narrative
        )
        if changed:
            content = {
                **content,
                "narrative": json.dumps(blocks) if isinstance(narrative, str) else blocks,
            }
            Revision.objects.using(alias).filter(pk=revision.pk).update(content=content)


class Migration(migrations.Migration):
    dependencies = [("public_content", "0019_case_study_narrative")]

    # Reversing must not put broken markup back into otherwise intact content.
    operations = [migrations.RunPython(repair_narratives, migrations.RunPython.noop)]
