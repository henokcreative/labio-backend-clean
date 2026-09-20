from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("public_content", "0017_team_members")]

    operations = [
        migrations.AddField(
            model_name="homepagefeaturedcasestudy",
            name="summary_override",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text="Optional homepage teaser. Leave blank to use the case study summary.",
            ),
        ),
    ]
