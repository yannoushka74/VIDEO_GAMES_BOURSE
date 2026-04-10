from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from django.db.models import Exists, F, Max, OuterRef, Q, Subquery

from .exchange import chf_to_eur, chf_to_usd, usd_to_chf
from .models import Game, Genre, Listing, Machine, Price
from .serializers import (
    GameDetailSerializer,
    GameListSerializer,
    GenreSerializer,
    MachineSerializer,
    PriceHistoryPointSerializer,
)

# Plateformes rétro collector uniquement
RETRO_SLUGS = ["neo", "nes", "snes", "gba", "saturn", "n64"]


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
    genre = filters.NumberFilter(field_name="genres__jvc_id")
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
    """Annonces Ricardo où le prix CHF (converti USD) est sous la cote PriceCharting.

    Filtrable par plateforme via ?platform=snes et limite via ?limit=100.
    Tri par décote décroissante.
    """
    limit = min(int(request.query_params.get("limit", 100)), 500)
    platform = request.query_params.get("platform", "")
    min_discount = float(request.query_params.get("min_discount", 20))  # %

    # On ne garde que les listings liés à un jeu (game_id non nul).
    # On exclut aussi les prix < 5 CHF (mises de départ d'enchères, non représentatives).
    listings_qs = (
        Listing.objects.filter(
            source="ricardo",
            game__isnull=False,
            current_price__gte=5,
        )
        .select_related("game")
        .prefetch_related("game__machines", "game__prices")
    )
    if platform:
        listings_qs = listings_qs.filter(platform_slug=platform)

    results = []
    for listing in listings_qs.iterator():
        game = listing.game
        # Cote PriceCharting la plus récente (loose comme référence)
        pc = game.prices.filter(source="pricecharting").order_by("-scraped_at").first()
        if not pc:
            continue
        # Référence : cib_price si dispo, sinon loose
        ref_usd = float(pc.cib_price) if pc.cib_price else float(pc.price)
        if ref_usd <= 0:
            continue

        # Prix de référence : achat direct si dispo (prix ferme), sinon current_price
        if listing.buy_now_price:
            price_chf = float(listing.buy_now_price)
        else:
            price_chf = float(listing.current_price)
        listing_chf = price_chf
        listing_usd = chf_to_usd(listing_chf)
        listing_eur = chf_to_eur(listing_chf)

        discount_pct = (1 - listing_usd / ref_usd) * 100
        if discount_pct < min_discount:
            continue

        machines = [m.name for m in game.machines.all() if m.slug in RETRO_SLUGS]

        results.append({
            "listing_id": listing.id,
            "game_id": game.id,
            "title": game.title,
            "cover_url": game.cover_url,
            "machines": machines,
            "platform_slug": listing.platform_slug,
            "listing_title": listing.title,
            "listing_url": listing.listing_url,
            "listing_image": listing.image_url,
            "listing_price_chf": round(listing_chf, 2),
            "listing_price_eur": round(listing_eur, 2),
            "listing_price_usd": round(listing_usd, 2),
            "bid_count": listing.bid_count,
            "ends_at": listing.ends_at.isoformat() if listing.ends_at else None,
            "ref_source": "cib" if pc.cib_price else "loose",
            "ref_price_usd": round(ref_usd, 2),
            "discount_percent": round(discount_pct, 1),
        })

    # Tri par décote décroissante
    results.sort(key=lambda r: r["discount_percent"], reverse=True)
    return Response(results[:limit])
