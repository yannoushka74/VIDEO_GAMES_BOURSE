"""Scanne les listings et notifie les alertes déclenchées.

Usage :
    python manage.py check_alerts                  # vérifie toutes les alertes actives
    python manage.py check_alerts --dry-run        # n'envoie rien, affiche juste
    python manage.py check_alerts --alert 42       # une alerte précise

Planifiable via cron ou Airflow toutes les 15 min.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from games.alerts import (
    convert_price,
    effective_listing_price,
    format_notification_text,
    listing_triggers_alert,
)
from games.models import Alert, AlertNotification, Listing
from games.notifier import send_telegram


class Command(BaseCommand):
    help = "Vérifie les alertes prix et envoie une notification Telegram par match."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="N'envoie rien.")
        parser.add_argument("--alert", type=int, default=None, help="ID d'une alerte précise.")
        parser.add_argument(
            "--window-hours",
            type=int,
            default=48,
            help="Ne considérer que les listings scrapés depuis N heures (défaut 48).",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        alert_id = opts["alert"]
        window_hours = opts["window_hours"]

        alerts_qs = Alert.objects.filter(is_active=True).select_related("game")
        if alert_id is not None:
            alerts_qs = alerts_qs.filter(id=alert_id)

        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=window_hours)

        total_alerts = 0
        total_notifs = 0
        total_skipped = 0

        for alert in alerts_qs:
            total_alerts += 1
            allowed = alert.allowed_sources()
            if not allowed:
                continue

            listings = Listing.objects.filter(
                game_id=alert.game_id,
                source__in=allowed,
                scraped_at__gte=cutoff,
            ).exclude(alert_notifications__alert=alert)

            for listing in listings:
                if not listing_triggers_alert(alert, listing):
                    continue

                converted = convert_price(
                    effective_listing_price(listing),
                    listing.currency,
                    alert.currency,
                )
                if converted is None:
                    continue

                text = format_notification_text(alert, listing, converted)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[MATCH] alert={alert.id} game={alert.game.title} "
                        f"listing={listing.id} price={converted} {alert.currency}"
                    )
                )

                if dry:
                    total_skipped += 1
                    continue

                sent = send_telegram(text)
                AlertNotification.objects.create(
                    alert=alert,
                    listing=listing,
                    price_at_notification=converted,
                    currency_at_notification=alert.currency,
                )
                if sent:
                    total_notifs += 1
                else:
                    total_skipped += 1

        self.stdout.write(
            self.style.NOTICE(
                f"Checked {total_alerts} active alerts — "
                f"{total_notifs} sent, {total_skipped} skipped/dry-run"
            )
        )
