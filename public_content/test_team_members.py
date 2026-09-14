from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from .models import AboutPage, HomePage, TeamMember
from .tests import ONE_PIXEL_GIF, TEST_STORAGES


@override_settings(STORAGES=TEST_STORAGES)
class TeamMemberTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        image = get_image_model().objects.create(title="Local portrait", file=SimpleUploadedFile("local.gif", ONE_PIXEL_GIF, content_type="image/gif"))
        cls.home = HomePage(
            title="Local team test", slug="local-team-test",
            hero_eyebrow="Studio", hero_heading="Local test", hero_copy="Local copy",
            hero_image=image, hero_image_alt="Local image",
            primary_cta_label="Work", primary_cta_url="https://example.com/work",
            secondary_cta_label="Contact", secondary_cta_url="https://example.com/contact",
            about_heading="About", about_copy="Local copy", about_image=image, about_image_alt="Local image",
            contact_heading="Contact", contact_copy="Local copy", contact_cta_label="Contact", contact_cta_url="https://example.com/contact",
        )
        root.add_child(instance=cls.home)
        cls.home.save_revision().publish()
        site = Site.objects.get(is_default_site=True)
        site.root_page = cls.home
        site.save()
        cls.about = AboutPage(title="About", slug="about", team_enabled=True, intro="Local intro", hero_image=image, hero_image_alt="Local image")
        cls.home.add_child(instance=cls.about)
        cls.about.save_revision().publish()
        cls.publisher = User.objects.create_superuser("publisher", "publisher@example.com", "test-password")
        cls.intern = User.objects.create_user("intern", password="test-password")
        group = Group.objects.create(name="Labio CMS Intern")
        group.permissions.add(*Permission.objects.filter(
            content_type__app_label="public_content",
            codename__in=["add_teammember", "change_teammember"],
        ))
        group.permissions.add(Permission.objects.get(codename="access_admin", content_type__app_label="wagtailadmin"))
        cls.intern.groups.add(group)

    def member(self, **kwargs):
        member = TeamMember.objects.create(name="Example Person", role="Producer", **kwargs)
        member.save_revision().publish()
        member.refresh_from_db()
        return member

    def payload(self):
        response = self.client.get(f"/api/cms/v2/pages/{self.about.pk}/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def url(self, action, member=None):
        return reverse(f"wagtailsnippets_public_content_teammember:{action}", args=[member.pk] if member else [])

    def form(self, **kwargs):
        return {"name": "Draft Person", "role": "Draft role", "biography": "Draft biography", "professional_url": "https://example.com/profile", "display_order": "7", "active": "on", **kwargs}

    def test_filtering_order_and_public_allowlist(self):
        later = self.member(display_order=5)
        first = self.member(display_order=0)
        tied = self.member(display_order=0)
        self.member(active=False)
        TeamMember.objects.create(name="Never published", role="Producer")
        draft = TeamMember.objects.create(name="Draft", role="Producer", live=False)
        draft.save_revision()
        items = self.payload()["team_members"]
        self.assertEqual([item["id"] for item in items], [first.pk, tied.pk, later.pk])
        self.assertEqual(set(items[0]), {"id", "name", "role", "portrait", "biography", "professional_url"})
        self.assertIsNone(items[0]["portrait"])

    def test_disabled_and_empty_sections(self):
        self.assertEqual(self.payload()["team_members"], [])
        self.member()
        self.about.team_enabled = False
        self.about.save_revision().publish()
        self.assertFalse(self.payload()["team_enabled"])
        self.assertEqual(self.payload()["team_members"], [])
        self.assertFalse(AboutPage().team_enabled)

    def test_portrait_rendition_and_deletion(self):
        image = get_image_model().objects.create(title="Portrait", file=SimpleUploadedFile("portrait.gif", ONE_PIXEL_GIF, content_type="image/gif"))
        self.member(portrait=image)
        portrait = self.payload()["team_members"][0]["portrait"]
        self.assertEqual(set(portrait), {"url", "width", "height", "alt"})
        self.assertEqual(portrait["alt"], "Portrait of Example Person")
        image.delete()
        self.assertIsNone(self.payload()["team_members"][0]["portrait"])

    def test_field_validation(self):
        for changes in [{"professional_url": url} for url in ["javascript:alert(1)", "ftp://example.com", "mailto:a@example.com", "//example.com", "/profile"]] + [{"display_order": -1}, {"biography": "x" * 1001}, {"name": ""}, {"role": ""}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                TeamMember(**{"name": "Person", "role": "Producer", **changes}).full_clean()
        for url in ["http://example.com", "https://example.com/profile"]:
            TeamMember(name="Person", role="Producer", professional_url=url).full_clean()

    def test_intern_can_create_only_drafts_even_with_publish_action(self):
        self.client.force_login(self.intern)
        self.assertEqual(self.client.get(self.url("add")).status_code, 200)
        for action in [{}, {"action-publish": "Publish"}]:
            response = self.client.post(self.url("add"), self.form(**action))
            self.assertEqual(response.status_code, 302)
        self.assertEqual(TeamMember.objects.count(), 2)
        for member in TeamMember.objects.all():
            self.assertFalse(member.live)
            self.assertIsNone(member.live_revision_id)
        self.assertEqual(self.payload()["team_members"], [])

    def test_intern_edit_preserves_all_live_fields_until_publisher_publishes(self):
        member = self.member(display_order=1)
        original = self.payload()["team_members"]
        image = get_image_model().objects.create(title="New portrait", file=SimpleUploadedFile("draft.gif", ONE_PIXEL_GIF, content_type="image/gif"))
        self.client.force_login(self.intern)
        response = self.client.post(self.url("edit", member), self.form(portrait=image.pk, **{"action-publish": "Publish"}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.payload()["team_members"], original)
        member.refresh_from_db()
        self.assertTrue(member.has_unpublished_changes)
        draft = member.get_latest_revision_as_object()
        self.assertEqual(draft.name, "Draft Person")
        self.assertEqual(draft.portrait_id, image.pk)
        self.client.force_login(self.publisher)
        response = self.client.post(self.url("edit", member), self.form(portrait=image.pk, **{"action-publish": "Publish"}))
        self.assertEqual(response.status_code, 302)
        published = self.payload()["team_members"][0]
        self.assertEqual(published["name"], "Draft Person")
        self.assertEqual(published["role"], "Draft role")
        self.assertEqual(published["biography"], "Draft biography")
        self.assertTrue(published["portrait"])
        member.refresh_from_db()
        self.assertEqual(member.display_order, 7)

    def test_draft_deactivation_does_not_hide_live_member(self):
        member = self.member()
        self.client.force_login(self.intern)
        form = self.form()
        form.pop("active")
        self.assertEqual(self.client.post(self.url("edit", member), form).status_code, 302)
        self.assertEqual(len(self.payload()["team_members"]), 1)
        self.client.force_login(self.publisher)
        self.assertEqual(self.client.post(self.url("edit", member), {**form, "action-publish": "Publish"}).status_code, 302)
        self.assertEqual(self.payload()["team_members"], [])

    def test_intern_cannot_unpublish_or_delete(self):
        member = self.member()
        self.client.force_login(self.intern)
        for action in ["unpublish", "delete"]:
            self.assertEqual(self.client.post(self.url(action, member), HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code, 403)
        member.refresh_from_db()
        self.assertTrue(member.live)
        self.assertFalse(self.intern.is_staff)
        for permission in ["publish_teammember", "delete_teammember", "add_group", "change_user"]:
            self.assertFalse(any(p.endswith("." + permission) for p in self.intern.get_all_permissions()))

    def test_publisher_can_unpublish(self):
        member = self.member()
        self.client.force_login(self.publisher)
        self.assertEqual(self.client.post(self.url("unpublish", member)).status_code, 302)
        self.assertEqual(self.payload()["team_members"], [])
