from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0011_alter_listing_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="title_en",
            field=models.CharField(blank=True, default="", help_text="Titre anglais (PriceCharting)", max_length=500),
            preserve_default=False,
        ),
    ]
