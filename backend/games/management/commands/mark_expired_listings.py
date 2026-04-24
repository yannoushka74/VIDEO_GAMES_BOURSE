"""Marque les listings Ricardo/eBay expirés en détachant du jeu.

Heuristiques :
1. Listings scrapés il y a plus de N jours (défaut 7) → probablement expirés
2. Pour Ricardo, les annonces qui n'apparaissent plus dans les scrapes
   sont supprimées automatiquement par --clear dans scrape_ricardo

Usage :
    python manage.py mark_expired_listings --days 7 --dry-run
    python manage.py mark_expired_listings --days 7
    python manage.py mark_expired_listings --days 7 --delete
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from games.models import Listing


class Command(BaseCommand):
    help = "Marque ou supprime les listings trop anciens (probablement expirés)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--delete", action="store_true",
            help="Supprimer au lieu de juste détacher du jeu",
        )
        parser.add_argument(
            "--source", type=str, default="",
            help="Filtrer par source (ricardo, ebay). Défaut: tous",
        )

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts["days"])
        qs = Listing.objects.filter(scraped_at__lt=cutoff)
        if opts["source"]:
            qs = qs.filter(source=opts["source"])

        total = qs.count()
        self.stdout.write(f"{total} listings scrapés avant {cutoff.date()}")

        if opts["dry_run"]:
            for l in qs[:10]:
                age_days = (timezone.now() - l.scraped_at).days
                self.stdout.write(f"  L{l.id} | {age_days}j | {l.source} | {l.title[:60]}")
            self.stdout.write(f"... ({total} au total) — DRY RUN")
            return

        if opts["delete"]:
            deleted = qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Supprimé: {deleted}"))
        else:
            # Marquer ends_at = scraped_at + 30 jours (estimation conservatrice)
            # Puis détacher du jeu pour qu'ils n'apparaissent plus dans les opportunities
            updated = qs.update(ends_at=cutoff, game=None)
            self.stdout.write(self.style.SUCCESS(f"{updated} listings détachés (ends_at marqué)"))
