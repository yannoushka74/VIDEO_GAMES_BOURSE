from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0012_game_title_en"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="pal_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Inconnu"),
                    ("pal", "Sorti en PAL"),
                    ("not_pal", "Pas de version PAL"),
                ],
                db_index=True,
                default="unknown",
                help_text="Statut PAL déterminé via IGDB release_dates",
                max_length=10,
            ),
        ),
    ]
