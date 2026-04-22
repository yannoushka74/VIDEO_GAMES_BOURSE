from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0016_remove_jvc_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="price",
            name="region",
            field=models.CharField(
                blank=True,
                default="",
                help_text="pal, ntsc, ou '' pour les sources sans distinction",
                max_length=10,
            ),
        ),
    ]
