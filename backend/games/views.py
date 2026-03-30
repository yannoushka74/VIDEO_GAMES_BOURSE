from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db.models import Max

from .models import Game, Genre, Listing, Machine, Price
from .serializers import (
    GameDetailSerializer,
    GameListSerializer,
    GenreSerializer,
    MachineSerializer,
)

# Plateformes rétro collector uniquement
RETRO_SLUGS = ["neo", "nes", "snes", "gba", "saturn", "n64"]


def _retro_games_qs():
    return Game.objects.filter(
        machines__slug__in=RETRO_SLUGS
    ).distinct().prefetch_related("machines", "genres", "prices", "listings")


def _retro_machines_qs():
    return Machine.objects.filter(slug__in=RETRO_SLUGS)


class GameFilter(filters.FilterSet):
    title = filters.CharFilter(lookup_expr="icontains")
    machine = filters.CharFilter(field_name="machines__slug")
    genre = filters.NumberFilter(field_name="genres__jvc_id")

    class Meta:
        model = Game
        fields = ["title", "machine", "genre"]


class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = _retro_games_qs()
    filterset_class = GameFilter
    search_fields = ["title"]
    ordering_fields = ["title", "release_date", "created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GameDetailSerializer
        return GameListSerializer


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
            "cib_price": str(pc_price.cib_price) if pc_price.cib_price else None,
            "new_price": str(pc_price.new_price) if pc_price.new_price else None,
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
