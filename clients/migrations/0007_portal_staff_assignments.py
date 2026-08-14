from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


PERMISSION_CODENAME = "access_private_portal_data"
GROUP_NAME = "Portal Staff"


def create_portal_staff_group(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="clients",
        model="project",
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=PERMISSION_CODENAME,
        defaults={"name": "Can access private LaBio client portal data"},
    )
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(permission)


def remove_portal_staff_group_permission(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group = Group.objects.filter(name=GROUP_NAME).first()
    permission = Permission.objects.filter(
        content_type__app_label="clients",
        content_type__model="project",
        codename=PERMISSION_CODENAME,
    ).first()
    if group and permission:
        group.permissions.remove(permission)


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0006_alter_projectfile_file"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="project",
            options={
                "permissions": [
                    (
                        "access_private_portal_data",
                        "Can access private LaBio client portal data",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="client",
            name="primary_contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="primary_contact_clients",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="primary_staff",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="primary_staff_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="team_members",
            field=models.ManyToManyField(
                blank=True,
                related_name="team_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            create_portal_staff_group,
            remove_portal_staff_group_permission,
        ),
    ]
