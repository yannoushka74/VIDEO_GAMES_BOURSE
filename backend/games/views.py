from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from django.db.models import Exists, F, Max, OuterRef, Q, Subquery
from django.utils import timezone

from .exchange import chf_to_eur, chf_to_usd, usd_to_chf
from .models import Alert, Game, Genre, Listing, Machine, Price, SaleRecord
from .serializers import (
    AlertSerializer,
    GameDetailSerializer,
    GameListSerializer,
    GenreSerializer,
    MachineSerializer,
    PriceHistoryPointSerializer,
)

# Plateformes rétro collector uniquement
RETRO_SLUGS = ["neo", "nes", "snes", "gba", "saturn", "n64", "ps1", "dreamcast"]


def _latest_pc_price_subquery():
    """Subquery: prix loose PriceCharting le plus récent par jeu."""
    return Subquery(
        Price.objects.filter(game=OuterRef("pk"), source="pricecharting")
        .order_by("-scraped_at")
        .values("price")[:1]
    )


def _has_pc_subquery():
    return Exists(Price.objects.filter(game=OuterRef("pk"), source="pricecharting"))


def _has_ricardo_subquery():
    return Exists(Listing.objects.filter(game=OuterRef("pk"), source="ricardo"))


def _retro_games_qs(include_unverified: bool = False):
    """Catalogue des jeux rétro.

    Par défaut, filtre sur les jeux dont on a une preuve PAL :
    - `pal_status='pal'` (vérifié via IGDB release_dates), OU
    - cote PriceCharting (le DAG ne matche que les consoles `pal_*`), OU
    - annonce Ricardo (Suisse → marché PAL).

    Exclut explicitement `pal_status='not_pal'` (vérifié non-PAL via IGDB).

    `include_unverified=True` désactive le filtre (montre tous les jeux).
    """
    qs = (
        Game.objects.filter(machines__slug__in=RETRO_SLUGS)
        .distinct()
        .prefetch_related("machines", "genres", "prices", "listings")
        .annotate(
            latest_loose_price=_latest_pc_price_subquery(),
            has_pc_price=_has_pc_subquery(),
            has_ricardo_listing=_has_ricardo_subquery(),
        )
    )
    if not include_unverified:
        # Exclure ce qui est vérifié non-PAL
        qs = qs.exclude(pal_status=Game.PalStatus.NOT_PAL)
        # Garder ce qui est positivement vérifié PAL OU a des preuves d'achat
        qs = qs.filter(
            Q(pal_status=Game.PalStatus.PAL)
            | Q(has_pc_price=True)
            | Q(has_ricardo_listing=True)
        )
    return qs


def _retro_machines_qs():
    return Machine.objects.filter(slug__in=RETRO_SLUGS)


class GameFilter(filters.FilterSet):
    title = filters.CharFilter(lookup_expr="icontains")
    machine = filters.CharFilter(field_name="machines__slug")
    genre = filters.CharFilter(field_name="genres__slug")
    price_min = filters.NumberFilter(field_name="latest_loose_price", lookup_expr="gte")
    price_max = filters.NumberFilter(field_name="latest_loose_price", lookup_expr="lte")
    has_price = filters.BooleanFilter(method="filter_has_price")

    class Meta:
        model = Game
        fields = ["title", "machine", "genre", "price_min", "price_max", "has_price"]

    def filter_has_price(self, queryset, name, value):
        if value:
            return queryset.filter(latest_loose_price__isnull=False)
        return queryset.filter(latest_loose_price__isnull=True)


class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Game.objects.none()  # remplacé par get_queryset
    filterset_class = GameFilter
    search_fields = ["title"]
    ordering_fields = ["title", "release_date", "created_at", "latest_loose_price"]

    def get_queryset(self):
        # Sur la page détail, on autorise l'accès direct même si le jeu n'est
        # pas PAL-vérifié (URL partagée, recherche directe, etc.)
        if self.action == "retrieve":
            return _retro_games_qs(include_unverified=True)
        include_unverified = (
            self.request.query_params.get("include_unverified", "").lower()
            in ("1", "true", "yes")
        )
        return _retro_games_qs(include_unverified=include_unverified)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GameDetailSerializer
        return GameListSerializer

    @action(detail=True, methods=["get"], url_path="price-history")
    def price_history(self, request, pk=None):
        """Historique complet des prix scrapés (toutes sources, ordre chronologique)."""
        game = self.get_object()
        prices = game.prices.order_by("scraped_at")
        return Response(PriceHistoryPointSerializer(prices, many=True).data)


class MachineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = _retro_machines_qs()
    serializer_class = MachineSerializer
    search_fields = ["name"]


class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    search_fields = ["name"]


class AlertViewSet(viewsets.ModelViewSet):
    """CRUD pour les alertes prix. Pas d'auth : un seul user (propriétaire du site)."""

    queryset = Alert.objects.select_related("game").all()
    serializer_class = AlertSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ["game", "is_active"]


@api_view(["GET"])
def api_stats(request):
    return Response({
        "games_count": _retro_games_qs().count(),
        "games_count_total": _retro_games_qs(include_unverified=True).count(),
        "machines_count": _retro_machines_qs().count(),
        "genres_count": Genre.objects.filter(games__machines__slug__in=RETRO_SLUGS).distinct().count(),
    })


@api_view(["GET"])
def top_expensive(request):
    """Top 200 jeux les plus chers (prix loose PriceCharting)."""
    limit = min(int(request.query_params.get("limit", 200)), 500)
    platform = request.query_params.get("platform", "")

    qs = (
        Game.objects
        .filter(machines__slug__in=RETRO_SLUGS, prices__source="pricecharting")
        .distinct()
    )
    if platform:
        qs = qs.filter(machines__slug=platform)

    qs = (
        qs.annotate(max_price=Max("prices__price"))
        .order_by("-max_price")
        .prefetch_related("machines", "prices", "listings")[:limit]
    )

    results = []
    for game in qs:
        pc_price = game.prices.filter(source="pricecharting").first()
        if not pc_price:
            continue
        machines = [m.name for m in game.machines.all() if m.slug in RETRO_SLUGS]

        # Prix Ricardo le moins cher
        ricardo_listing = game.listings.filter(source="ricardo").order_by("current_price").first()

        results.append({
            "id": game.id,
            "title": game.title,
            "cover_url": game.cover_url,
            "machines": machines,
            "loose_price": str(pc_price.price),
            "loose_price_chf": str(usd_to_chf(float(pc_price.price))),
            "cib_price": str(pc_price.cib_price) if pc_price.cib_price else None,
            "cib_price_chf": str(usd_to_chf(float(pc_price.cib_price))) if pc_price.cib_price else None,
            "new_price": str(pc_price.new_price) if pc_price.new_price else None,
            "new_price_chf": str(usd_to_chf(float(pc_price.new_price))) if pc_price.new_price else None,
            "graded_price": str(pc_price.graded_price) if pc_price.graded_price else None,
            "currency": pc_price.currency,
            "ricardo_price": str(ricardo_listing.current_price) if ricardo_listing else None,
            "ricardo_url": ricardo_listing.listing_url if ricardo_listing else None,
            "ricardo_bids": ricardo_listing.bid_count if ricardo_listing else None,
        })

    return Response(results)


@api_view(["GET"])
def autocomplete(request):
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return Response([])
    games = (
        _retro_games_qs()
        .filter(title__icontains=q)
        .values("id", "title", "cover_url")[:10]
    )
    return Response(list(games))


@api_view(["GET"])
def exchange_rates(request):
    """Taux de change du jour (cache 24h via Frankfurter.app)."""
    from .exchange import get_rate
    return Response({
        "usd_to_chf": get_rate("USD", "CHF"),
        "chf_to_usd": round(1 / (get_rate("USD", "CHF") or 0.79), 5),
        "usd_to_eur": get_rate("USD", "EUR"),
        "chf_to_eur": get_rate("CHF", "EUR"),
    })


@api_view(["GET"])
def opportunities(request):
    """Annonces Ricardo/eBay sous la cote PriceCharting.

    Optimisé : préchargement en 1 seul query SQL + cache 5 min.
    Utilise Price.region (pal/ntsc) pour matcher la bonne cote selon
    la région du listing (PAL par défaut, NTSC si flag).
    """
    from django.core.cache import cache
    import hashlib, json

    limit = min(int(request.query_params.get("limit", 100)), 500)
    platform = request.query_params.get("platform", "")
    min_discount = float(request.query_params.get("min_discount", 20))
    source_filter = request.query_params.get("source", "")

    # Cache 5 min par combinaison de params
    cache_key = "opp:" + hashlib.md5(
        f"{limit}:{platform}:{min_discount}:{source_filter}".encode()
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    from .exchange import get_rate
    usd_chf = get_rate("USD", "CHF") or 0.79
    chf_eur = get_rate("CHF", "EUR") or 1.09
    usd_eur = get_rate("USD", "EUR") or 0.86

    # 1. Récupérer les listings actifs (1 query)
    # Exclure les listings expirés (ends_at dépassé) et ceux scrapés il y a
    # plus de 14 jours (probablement expirés, pas re-vus dans les scrapes).
    from datetime import timedelta
    from django.db.models import Q
    now = timezone.now()
    cutoff = now - timedelta(days=14)
    qs = (
        Listing.objects.filter(
            source__in=["ricardo", "ebay"],
            game__isnull=False,
            current_price__gte=5,
            scraped_at__gte=cutoff,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .select_related("game")
        .prefetch_related("game__machines")
    )
    if source_filter:
        qs = qs.filter(source=source_filter)
    if platform:
        qs = qs.filter(platform_slug=platform)

    from scrapers.matching import is_alien_platform_listing, is_likely_accessory

    # Filtrer les listings aliens/accessoires avant le traitement lourd
    raw_listings = list(qs)
    listings = []
    for l in raw_listings:
        if is_likely_accessory(l.title):
            continue
        if is_alien_platform_listing(l.title, l.platform_slug):
            continue
        listings.append(l)
    game_ids = {l.game_id for l in listings}

    # Mapping console → substring attendu dans product_url PriceCharting
    # Permet de filtrer le prix selon la console du listing (jeux multi-plateforme).
    SLUG_TO_PC_URL = {
        "snes": "super-nintendo",
        "nes": "/nes/",
        "n64": "nintendo-64",
        "gba": "gameboy-advance",
        "saturn": "sega-saturn",
        "neo": "neo-geo",
        "ps1": "/playstation",  # attention: pas playstation-2
        "dreamcast": "sega-dreamcast",
    }

    # 2. Précharger TOUS les prix PC pertinents en 1 query SQL.
    #    Clé : (game_id, region, console_slug) pour gérer multi-plateforme.
    prices_by_key = {}
    for p in (Price.objects.filter(game_id__in=game_ids, source="pricecharting")
              .only("game_id", "region", "price", "cib_price", "new_price",
                    "graded_price", "product_url", "scraped_at")
              .order_by("-scraped_at")):
        region = p.region or "pal"
        # Déterminer la console depuis product_url
        url = (p.product_url or "").lower()
        console_slug = ""
        for slug, pc_sub in SLUG_TO_PC_URL.items():
            if pc_sub in url:
                console_slug = slug
                break
        key = (p.game_id, region, console_slug)
        if key not in prices_by_key:
            prices_by_key[key] = p

    # 3. Iteration en mémoire (plus de queries SQL)
    results = []
    for listing in listings:
        # Choisir la région de cote à utiliser selon la région du listing
        listing_region_up = (listing.region or "").upper()
        if listing_region_up == "NTSC":
            desired_region = "ntsc"
        elif listing_region_up == "JP":
            continue  # pas de cote PC fiable pour JP
        else:
            desired_region = "pal"

        # Chercher le prix pour la CONSOLE exacte du listing
        console_slug = listing.platform_slug
        price = prices_by_key.get((listing.game_id, desired_region, console_slug))
        # Fallback région : si PAL absent pour cette console, essayer NTSC
        if not price:
            other_region = "ntsc" if desired_region == "pal" else "pal"
            price = prices_by_key.get((listing.game_id, other_region, console_slug))
        if not price or not price.price:
            continue

        condition = listing.condition or "loose"
        if condition == "cib" and price.cib_price:
            ref_usd = float(price.cib_price)
            ref_source = "cib"
        elif condition == "new" and price.new_price:
            ref_usd = float(price.new_price)
            ref_source = "new"
        elif condition == "graded" and price.graded_price:
            ref_usd = float(price.graded_price)
            ref_source = "graded"
        else:
            ref_usd = float(price.price)
            ref_source = "loose"
        if ref_usd <= 0:
            continue

        raw_price = float(listing.buy_now_price or listing.current_price)
        cur = listing.currency
        if cur == "CHF":
            listing_chf = raw_price
            listing_usd = round(raw_price / usd_chf, 2)
            listing_eur = round(raw_price * chf_eur, 2)
        elif cur == "EUR":
            listing_eur = raw_price
            listing_usd = round(raw_price / usd_eur, 2)
            listing_chf = round(raw_price / chf_eur, 2)
        else:
            listing_usd = raw_price
            listing_chf = round(raw_price * usd_chf, 2)
            listing_eur = round(raw_price * usd_eur, 2)

        discount_pct = (1 - listing_usd / ref_usd) * 100
        if discount_pct < min_discount:
            continue

        g = listing.game
        machines = [m.name for m in g.machines.all() if m.slug in RETRO_SLUGS]

        results.append({
            "listing_id": listing.id,
            "game_id": g.id,
            "title": g.title,
            "cover_url": g.cover_url,
            "machines": machines,
            "platform_slug": listing.platform_slug,
            "listing_title": listing.title,
            "listing_url": listing.listing_url,
            "listing_image": listing.image_url,
            "listing_price_chf": round(listing_chf, 2),
            "listing_price_eur": round(listing_eur, 2),
            "listing_price_usd": round(listing_usd, 2),
            "listing_currency": cur,
            "listing_condition": condition,
            "listing_source": listing.source,
            "bid_count": listing.bid_count,
            "ends_at": listing.ends_at.isoformat() if listing.ends_at else None,
            "ref_source": ref_source,
            "ref_region": desired_region,
            "ref_price_usd": round(ref_usd, 2),
            "discount_percent": round(discount_pct, 1),
        })

    results.sort(key=lambda r: r["discount_percent"], reverse=True)
    results = results[:limit]

    # Cache 5 min
    cache.set(cache_key, results, 300)
    return Response(results)


@api_view(["GET"])
def market_cote(request):
    """Cote marché réelle basée sur les ventes effectives (SaleRecord).

    Params :
    - game_id : cote pour un jeu précis
    - platform : filtrer par console
    - condition : loose/cib/new/graded
    - source : ricardo, ebay
    - days : uniquement les ventes des N derniers jours (défaut 365)

    Retourne :
    - count, avg, median, min, max, stddev par condition
    - currency unifiée (CHF)
    - sales récentes pour illustration
    """
    from datetime import timedelta
    from decimal import Decimal
    from statistics import median, stdev

    game_id = request.query_params.get("game_id")
    platform = request.query_params.get("platform", "")
    condition = request.query_params.get("condition", "")
    source = request.query_params.get("source", "")
    days = int(request.query_params.get("days", 365))

    from .exchange import get_rate
    usd_chf = get_rate("USD", "CHF") or 0.79
    eur_chf = 1 / (get_rate("CHF", "EUR") or 1.09)

    cutoff = timezone.now() - timedelta(days=days)
    qs = SaleRecord.objects.filter(sold_at__gte=cutoff)
    if game_id:
        qs = qs.filter(game_id=int(game_id))
    if platform:
        qs = qs.filter(platform_slug=platform)
    if source:
        qs = qs.filter(source=source)

    # Agréger par condition, en CHF
    by_condition = {}
    for sale in qs.iterator():
        cond = sale.condition or "loose"
        if condition and cond != condition:
            continue
        # Convertir en CHF
        price = float(sale.final_price)
        if sale.currency == "CHF":
            price_chf = price
        elif sale.currency == "EUR":
            price_chf = price / (get_rate("CHF", "EUR") or 1.09)
        elif sale.currency == "USD":
            price_chf = price * usd_chf
        else:
            price_chf = price
        by_condition.setdefault(cond, []).append(price_chf)

    def _stats(prices: list[float]) -> dict:
        if not prices:
            return {}
        return {
            "count": len(prices),
            "avg": round(sum(prices) / len(prices), 2),
            "median": round(median(prices), 2),
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "stddev": round(stdev(prices), 2) if len(prices) > 1 else 0,
        }

    result = {
        "currency": "CHF",
        "period_days": days,
        "by_condition": {c: _stats(p) for c, p in by_condition.items()},
        "total_sales": sum(len(p) for p in by_condition.values()),
    }

    # Ventes récentes pour illustration (20 max)
    recent = qs.order_by("-sold_at")[:20]
    result["recent_sales"] = [
        {
            "final_price": str(s.final_price),
            "currency": s.currency,
            "condition": s.condition,
            "region": s.region,
            "platform_slug": s.platform_slug,
            "listing_title": s.listing_title[:80],
            "listing_url": s.listing_url,
            "source": s.source,
            "sold_at": s.sold_at.isoformat(),
        }
        for s in recent
    ]

    return Response(result)
