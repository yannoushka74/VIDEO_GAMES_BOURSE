import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0017_price_region"),
    ]

    operations = [
        migrations.CreateModel(
            name="SaleRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("ricardo", "Ricardo"), ("ebay", "eBay")], max_length=20)),
                ("platform_slug", models.SlugField(max_length=20)),
                ("final_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="CHF", max_length=3)),
                ("condition", models.CharField(blank=True, max_length=100)),
                ("region", models.CharField(blank=True, max_length=10)),
                ("listing_title", models.CharField(max_length=500)),
                ("listing_url", models.URLField(max_length=500)),
                ("sold_at", models.DateTimeField(auto_now_add=True)),
                (
                    "game",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sales", to="games.game",
                    ),
                ),
            ],
            options={
                "ordering": ["-sold_at"],
                "indexes": [
                    models.Index(fields=["game", "platform_slug", "-sold_at"], name="games_saler_game_id_plat_idx"),
                    models.Index(fields=["source", "-sold_at"], name="games_saler_source_sold_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["source", "listing_url"], name="uniq_sale_source_url"),
                ],
            },
        ),
    ]
