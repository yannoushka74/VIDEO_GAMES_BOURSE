"""Archive les Listings expirés en SaleRecord.

Un Listing est considéré comme vendu/terminé si :
- Il n'a pas été re-scrapé depuis N jours (défaut 7)
- Son `ends_at` est dépassé

Au lieu de les supprimer, on les archive comme SaleRecord (cote marché).

Usage :
    python manage.py archive_expired_listings --days 7 --dry-run
    python manage.py archive_expired_listings --days 7
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from games.models import Listing, SaleRecord


class Command(BaseCommand):
    help = "Archive les Listings expirés en SaleRecord."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--source", type=str, default="")
        parser.add_argument("--delete-after", action="store_true",
                            help="Supprime le Listing après archivage")

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts["days"])
        qs = Listing.objects.filter(
            source__in=["ricardo", "ebay"],
            scraped_at__lt=cutoff,
        )
        if opts["source"]:
            qs = qs.filter(source=opts["source"])

        total = qs.count()
        self.stdout.write(f"{total} listings expirés (scraped_at < {cutoff.date()})")

        if opts["dry_run"]:
            for l in qs[:15]:
                age = (timezone.now() - l.scraped_at).days
                self.stdout.write(f"  L{l.id} | {l.source} | {age}j | {l.current_price} {l.currency} | {l.title[:55]}")
            self.stdout.write(f"... ({total} au total) — DRY RUN")
            return

        created = 0
        skipped = 0
        deleted = 0

        for l in qs.iterator():
            # final_price = buy_now_price si défini (achat immédiat), sinon current_price
            final_price = l.buy_now_price or l.current_price
            _, was_created = SaleRecord.objects.get_or_create(
                source=l.source,
                listing_url=l.listing_url,
                defaults={
                    "game": l.game,
                    "platform_slug": l.platform_slug,
                    "final_price": final_price,
                    "currency": l.currency,
                    "condition": l.condition or "loose",
                    "region": l.region or "",
                    "listing_title": l.title[:500],
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1
            if opts["delete_after"]:
                l.delete()
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} archivés, {skipped} déjà en base"
                + (f", {deleted} listings supprimés" if opts["delete_after"] else "")
            )
        )
