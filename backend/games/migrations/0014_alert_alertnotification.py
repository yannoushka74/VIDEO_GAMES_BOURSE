# Generated manually for Alert / AlertNotification models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0013_game_pal_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Alert",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("max_price", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "currency",
                    models.CharField(
                        choices=[("CHF", "CHF"), ("EUR", "EUR"), ("USD", "USD")],
                        default="CHF",
                        max_length=3,
                    ),
                ),
                (
                    "sources",
                    models.CharField(
                        default="ricardo,ebay",
                        help_text="Sources autorisées séparées par virgule (ricardo,ebay,leboncoin)",
                        max_length=100,
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alerts",
                        to="games.game",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["game", "is_active"], name="games_alert_game_id_active_idx"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="AlertNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("price_at_notification", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency_at_notification", models.CharField(max_length=3)),
                ("notified_at", models.DateTimeField(auto_now_add=True)),
                (
                    "alert",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="games.alert",
                    ),
                ),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_notifications",
                        to="games.listing",
                    ),
                ),
            ],
            options={
                "ordering": ["-notified_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("alert", "listing"), name="uniq_alert_listing"
                    )
                ],
            },
        ),
    ]
