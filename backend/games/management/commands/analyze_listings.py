"""Analyse les listings avec le pipeline ML (condition + console + région).

Wrapper Django du script ml/analyze_listings.py pour pouvoir être
appelé via `manage.py` (donc via KubernetesPodOperator dans Airflow).

Usage :
    python manage.py analyze_listings                       # tous listings
    python manage.py analyze_listings --source ebay
    python manage.py analyze_listings --source ricardo --no-console
    python manage.py analyze_listings --limit 500
"""

from django.core.management.base import BaseCommand

from games.models import Listing


class Command(BaseCommand):
    help = "Analyse les listings via pipeline ML (condition + console + région)"

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, help="Filtrer par source (ebay, ricardo)")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-ocr", action="store_true")
        parser.add_argument("--no-console", action="store_true")
        parser.add_argument("--condition-threshold", type=float, default=0.7)
        parser.add_argument("--console-threshold", type=float, default=0.6)
        parser.add_argument(
            "--only-unanalyzed", action="store_true",
            help="Ne traiter que les listings jamais analysés (via SemiColon tag)",
        )

    def handle(self, *args, **opts):
        from ml.pipeline import ListingAnalyzer

        analyzer = ListingAnalyzer(
            condition_threshold=opts["condition_threshold"],
            console_threshold=opts["console_threshold"],
            enable_ocr=not opts["no_ocr"],
        )

        qs = (
            Listing.objects.exclude(image_url="")
            .exclude(image_url__icontains=".svg")
            .order_by("-scraped_at")
        )
        if opts["source"]:
            qs = qs.filter(source=opts["source"])
        if opts["limit"] > 0:
            qs = qs[:opts["limit"]]

        total = qs.count() if opts["limit"] == 0 else min(opts["limit"], qs.count())
        self.stdout.write(f"{total} listings à analyser...")
        self.stdout.write(f"OCR: {'ON' if not opts['no_ocr'] else 'OFF'}")
        self.stdout.write(f"Console: {'ON' if not opts['no_console'] else 'OFF'}")

        cond_changed = 0
        console_mismatch = 0
        jp_detected = 0

        for i, listing in enumerate(qs.iterator(), 1):
            result = analyzer.analyze(
                listing.image_url,
                listing.platform_slug,
                listing.condition or "loose",
            )
            changed = False
            if result["condition_source"] == "image" and result["condition"] != (listing.condition or "loose"):
                if not opts["dry_run"]:
                    listing.condition = result["condition"]
                    changed = True
                cond_changed += 1
            if "console_mismatch" in result["flags"]:
                console_mismatch += 1
            if "region_mismatch" in result["flags"]:
                jp_detected += 1
                if not opts["dry_run"] and listing.region != "JP":
                    listing.region = "JP"
                    changed = True
            if changed:
                listing.save(update_fields=["condition", "region"])
            if i % 200 == 0:
                self.stdout.write(
                    f"  {i}/{total} — cond:{cond_changed} console:{console_mismatch} jp:{jp_detected}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé — cond:{cond_changed} console:{console_mismatch} jp:{jp_detected} "
                f"{'(DRY RUN)' if opts['dry_run'] else ''}"
            )
        )
