from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0018_salerecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="listing",
            name="description_fetched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
