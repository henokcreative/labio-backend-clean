from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("public_content", "0020_repair_narrative_line_breaks")]

    operations = [
        migrations.AddField(
            model_name="teammember",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
