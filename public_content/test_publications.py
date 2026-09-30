from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.documents import get_document_model

from .blocks import PrintDesignBlock
from .models import Publication
from .tests import TEST_STORAGES


@override_settings(STORAGES=TEST_STORAGES)
class PublicationTests(TestCase):
    def setUp(self):
        self.document = get_document_model().objects.create(
            title="Report", file=SimpleUploadedFile("report.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
        )

    def publication(self, slug, **kwargs):
        publication = Publication.objects.create(
            title="Report", slug=slug, pdf_file=self.document, **kwargs,
        )
        publication.save_revision().publish()
        return publication

    def test_public_only_order_allowlist_and_optional_fields(self):
        later = self.publication("later", is_public=True, sort_order=2)
        first = self.publication("first", is_public=True)
        self.publication("private")
        Publication.objects.create(title="Unpublished", slug="unpublished", pdf_file=self.document, is_public=True)
        response = self.client.get(reverse("cms-publications"))
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual([item["id"] for item in items], [first.pk, later.pk])
        self.assertEqual(set(items[0]), {"id", "title", "slug", "short_description", "publication_year", "cover_image", "pdf_url"})
        self.assertIsNone(items[0]["cover_image"])
        self.assertIsNone(items[0]["publication_year"])
        self.assertEqual(items[0]["short_description"], "")
        self.assertEqual(items[0]["pdf_url"], self.document.url)

    def test_draft_edits_and_public_visibility(self):
        publication = self.publication("report", is_public=True)
        publication.title = "Unpublished title"
        publication.is_public = False
        revision = publication.save_revision()
        self.assertEqual(self.client.get(reverse("cms-publications")).json()[0]["title"], "Report")
        revision.publish()
        self.assertEqual(self.client.get(reverse("cms-publications")).json(), [])

    def test_required_fields_and_pdf_validation(self):
        with self.assertRaises(ValidationError):
            Publication(slug="missing").full_clean()
        Publication(title="Report", slug="report", pdf_file=self.document).full_clean()
        other = get_document_model().objects.create(
            title="Not PDF", file=SimpleUploadedFile("notes.txt", b"text"),
        )
        with self.assertRaises(ValidationError):
            Publication(title="Report", slug="report", pdf_file=other).full_clean()

    def test_print_design_reference_and_published_serialization(self):
        publication = self.publication("print", is_public=True)
        block = PrintDesignBlock()
        value = block.to_python({"publication": publication.pk})
        self.assertEqual(block.get_prep_value(value), {"publication": publication.pk})
        expected = self.client.get(reverse("cms-publications")).json()[0]
        self.assertEqual(block.get_api_representation(value), {"publication": expected})
        publication.title = "Draft title"
        publication.is_public = False
        revision = publication.save_revision()
        self.assertEqual(block.get_api_representation({"publication": publication}), {"publication": expected})
        revision.publish()
        self.assertEqual(block.get_api_representation(value), {"publication": None})

    def test_print_design_unpublished_and_deleted_are_safe(self):
        publication = Publication.objects.create(title="Draft", slug="draft", pdf_file=self.document, is_public=True)
        block = PrintDesignBlock()
        value = block.to_python({"publication": publication.pk})
        self.assertEqual(block.get_api_representation(value), {"publication": None})
        pk = publication.pk
        publication.delete()
        self.assertEqual(block.get_api_representation(block.to_python({"publication": pk})), {"publication": None})
