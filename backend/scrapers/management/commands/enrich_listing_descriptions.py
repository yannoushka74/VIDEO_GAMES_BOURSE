"""Enrichit les Listings avec leur description complète.

Pour Ricardo : fetch via Botasaurus (page détail JS-rendered).
Pour eBay : fetch via Browse API getItem.

Usage :
    python manage.py enrich_listing_descriptions --source ricardo --limit 100
    python manage.py enrich_listing_descriptions --source ebay --limit 200
    python manage.py enrich_listing_descriptions --reanalyze   # filtre repros après enrichissement
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from games.models import Listing
from scrapers.matching import is_likely_accessory


class Command(BaseCommand):
    help = "Fetch les descriptions des listings (Ricardo via Botasaurus, eBay via API)"

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, choices=["ricardo", "ebay"], required=True)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--platform", type=str, default="")
        parser.add_argument(
            "--only-missing", action="store_true", default=True,
            help="Skip les listings ayant déjà une description",
        )
        parser.add_argument(
            "--reanalyze", action="store_true",
            help="Après enrichissement, dé-matcher les listings dont la description trahit un repro",
        )

    def handle(self, *args, **opts):
        qs = Listing.objects.filter(source=opts["source"])
        if opts["platform"]:
            qs = qs.filter(platform_slug=opts["platform"])
        if opts["only_missing"]:
            qs = qs.filter(description="")
        # Prioriser : listings matchés (game != null) > listings non-matchés
        # Plus utile pour les opportunities
        qs = qs.order_by("-game_id", "-scraped_at")[:opts["limit"]]
        listings = list(qs)
        self.stdout.write(f"{len(listings)} listings à enrichir ({opts['source']})")

        if not listings:
            return

        if opts["source"] == "ricardo":
            self._enrich_ricardo(listings)
        else:
            self._enrich_ebay(listings)

        if opts["reanalyze"]:
            self._filter_repros(opts["source"])

    def _enrich_ricardo(self, listings: list[Listing]):
        from scrapers.ricardo import fetch_ricardo_descriptions

        urls = [l.listing_url for l in listings]
        descs = fetch_ricardo_descriptions(urls)
        now = timezone.now()
        updated = 0
        for l in listings:
            desc = descs.get(l.listing_url, "")
            if desc:
                l.description = desc[:10000]
                l.description_fetched_at = now
                l.save(update_fields=["description", "description_fetched_at"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Ricardo : {updated}/{len(listings)} enrichis"))

    def _enrich_ebay(self, listings: list[Listing]):
        from scrapers.ebay import extract_ebay_item_id, fetch_ebay_description

        now = timezone.now()
        updated = 0
        for i, l in enumerate(listings, 1):
            item_id = extract_ebay_item_id(l.listing_url)
            if not item_id:
                continue
            desc = fetch_ebay_description(item_id)
            if desc:
                l.description = desc[:10000]
                l.description_fetched_at = now
                l.save(update_fields=["description", "description_fetched_at"])
                updated += 1
            if i % 50 == 0:
                self.stdout.write(f"  {i}/{len(listings)} ({updated} avec desc)")
        self.stdout.write(self.style.SUCCESS(f"eBay : {updated}/{len(listings)} enrichis"))

    def _filter_repros(self, source: str):
        """Détache (game=None) les listings dont la description révèle un repro."""
        qs = Listing.objects.filter(source=source).exclude(description="").exclude(game__isnull=True)
        unmatched = 0
        for l in qs.iterator():
            if is_likely_accessory(l.title, l.description):
                l.game = None
                l.save(update_fields=["game"])
                unmatched += 1
        self.stdout.write(self.style.SUCCESS(f"Repros détachés : {unmatched}"))
