"""Remove jvc_id from Machine, Genre, and Game models."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0015_game_pricecharting_url"),
    ]

    operations = [
        migrations.RemoveField(model_name="machine", name="jvc_id"),
        migrations.RemoveField(model_name="genre", name="jvc_id"),
        migrations.RemoveField(model_name="game", name="jvc_id"),
    ]
