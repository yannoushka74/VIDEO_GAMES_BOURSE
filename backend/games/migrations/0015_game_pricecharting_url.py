from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0014_alert_alertnotification"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="pricecharting_url",
            field=models.URLField(
                blank=True,
                help_text="URL produit PriceCharting (identifiant catalogue primaire)",
                max_length=500,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="game",
            name="jvc_id",
            field=models.IntegerField(
                blank=True,
                help_text="ID jeuxvideo.com (legacy)",
                null=True,
                unique=True,
            ),
        ),
    ]
