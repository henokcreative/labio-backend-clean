# Team Members

TeamMember is a public-content snippet, separate from user, staff and client records.
The About API embeds published, active members in display_order / primary-key order.
The About page must also have its Team enabled setting published. It starts disabled.
No separate member endpoint or per-page selection is required.

## Local migration and validation

Use an environment installed from this repository's requirements.txt. Confirm that
DATABASE_URL targets a disposable local database, DJANGO_ENV is development,
RENDER is false, and CMS media storage is local. Do not load production credentials.
From the current backend repository, using that environment's Python:

```sh
python manage.py migrate
python manage.py test public_content
python manage.py makemigrations --check --dry-run
```

Only run these commands after confirming the local database and storage settings.
The new migration is public_content/0017_team_members.py; it creates no people and
changes no groups. Tests create their own temporary records.

From the current frontend repository:

```sh
npm run test:cms
npm run lint
npm run build
```

For local integration checks, explicitly set CMS_API_URL and NEXT_PUBLIC_API_URL
to your local backend before starting Next.js. Existing .env.local values must not
route a local test to production. A normal build also loads Google fonts; offline
validation can use Next's temporary font-response fixture without editing app code.

## Least-privilege Wagtail setup

As an authorized administrator of the LOCAL CMS:

1. Open Settings > Groups and edit the existing `Labio CMS Intern` group.
2. In snippet/model permissions, locate Team members.
3. Select Add and Change only. Leave Publish and Delete unselected, along with
   any additional TeamMember permissions. Unpublish is governed by Publish.
4. Preserve all unrelated permissions and existing page/image collection access.
5. Save. Repeating these steps makes no additional changes.
6. Check that the intern has no direct or other-group grants for TeamMember
   publishing/deletion. Django permissions are additive. Do not grant superuser,
   Django admin/staff status, portal roles or group-management access.

The intern can create and edit drafts. An existing authorized publisher reviews
them under Snippets > Team members and publishes them. This follows the existing
snippet draft/publish pattern; it does not add a formal moderation workflow.

## Manage the section

- Add name and role. Portrait, biography and professional HTTP(S) URL are optional.
- Use plain text for biography (maximum 1,000 characters).
- Set a nonnegative Display order. Lower values appear first; equal values use ID.
- Publish the member. Saving a draft alone does not update the public record.
- Edit About, enable Team, set its heading, and have an authorized page publisher
  publish the page. A newly published active member then appears automatically.
- To remove someone from display, uncheck Active and publish the change, or have
  a publisher unpublish the member. An intern's draft deactivation stays private.
- Replace a portrait by selecting/uploading another image and publishing the
  member change. Shared Wagtail images are separate resources: changing/deleting
  an existing image can affect other content. Portrait assets are public media.
- Only publish professional information and approved portraits. There are no
  email, phone or CV fields in this feature.

The frontend uses the existing 60-second revalidation policy. A cached page may
continue to show the previous publication while revalidation completes. There is
no new instant invalidation or deployment mechanism.

## Visual acceptance

Check the local About page on desktop and mobile with zero, one and several
published members; missing portraits; long names/roles/biographies; and light/dark
appearance. Confirm keyboard-visible profile links, no horizontal overflow, and
that Values, Process and Testimonials retain their position and appearance.
Real portraits, final copy, crops and production font appearance require editorial
review. No production deployment is performed by the implementation.

## Implementation validation record

- Backend: 52 public-content tests passed, including 9 TeamMember tests.
  Validation used Django 5.2.17 / Wagtail 7.4.3 from the declared requirements,
  an in-memory SQLite database, in-memory storage and blocked network connections.
- Migration consistency: no changes detected.
- Frontend: 33 CMS/parser/resolver tests passed; ESLint passed.
- Next.js production build passed using a localhost synthetic CMS and a local
  font fixture. Temporary test fixtures were outside the repositories. The
  production font download and actual production content were not tested.
- The built About page was checked with three synthetic members, including one
  without a portrait, in desktop/mobile layouts and light/dark appearance.
  Final real-content/crop/font review remains manual.
- Empty-team integration check passed after normal cache revalidation: no team
  section remained, while About content and Values remained visible. Desktop and
  mobile DOM measurements showed no horizontal document overflow.
