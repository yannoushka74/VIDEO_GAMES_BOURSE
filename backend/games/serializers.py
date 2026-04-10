from rest_framework import serializers

from .exchange import usd_to_chf
from .models import Game, Genre, Listing, Machine, Price


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ["id", "jvc_id", "name", "slug"]


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "jvc_id", "name", "slug"]


class PriceSerializer(serializers.ModelSerializer):
    price_chf = serializers.SerializerMethodField()
    cib_price_chf = serializers.SerializerMethodField()
    new_price_chf = serializers.SerializerMethodField()
    graded_price_chf = serializers.SerializerMethodField()

    class Meta:
        model = Price
        fields = [
            "id", "source", "price", "old_price", "discount_percent", "currency",
            "cib_price", "new_price", "graded_price", "box_only_price", "manual_only_price",
            "price_chf", "cib_price_chf", "new_price_chf", "graded_price_chf",
            "product_url", "product_title", "asin", "image_url",
            "rating", "review_count", "availability", "category", "scraped_at",
        ]

    def _to_chf(self, obj, field):
        val = getattr(obj, field, None)
        if val is None or obj.currency != "USD":
            return None
        return str(usd_to_chf(float(val)))

    def get_price_chf(self, obj):
        return self._to_chf(obj, "price")

    def get_cib_price_chf(self, obj):
        return self._to_chf(obj, "cib_price")

    def get_new_price_chf(self, obj):
        return self._to_chf(obj, "new_price")

    def get_graded_price_chf(self, obj):
        return self._to_chf(obj, "graded_price")


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            "id", "source", "platform_slug", "title", "listing_url", "image_url",
            "current_price", "buy_now_price", "currency",
            "bid_count", "ends_at", "condition", "region", "scraped_at",
        ]


class GameListSerializer(serializers.ModelSerializer):
    machines = MachineSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    latest_price = serializers.SerializerMethodField()
    latest_loose_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    listing_count = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id", "jvc_id", "title", "game_type", "release_date", "cover_url",
            "machines", "genres", "latest_price", "latest_loose_price", "listing_count",
        ]

    def get_latest_price(self, obj):
        price = obj.prices.first()
        if price:
            return {"price": str(price.price), "currency": price.currency, "source": price.source}
        return None

    def get_listing_count(self, obj):
        return obj.listings.count()


class PriceHistoryPointSerializer(serializers.ModelSerializer):
    """Point d'historique de prix : un snapshot d'un Price scrapé."""

    class Meta:
        model = Price
        fields = [
            "id", "source", "price", "cib_price", "new_price", "graded_price",
            "currency", "scraped_at",
        ]


class GameDetailSerializer(serializers.ModelSerializer):
    machines = MachineSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    game_type_display = serializers.CharField(source="get_game_type_display", read_only=True)
    prices = serializers.SerializerMethodField()
    listings = ListingSerializer(many=True, read_only=True)

    class Meta:
        model = Game
        fields = [
            "id", "jvc_id", "title", "title_en", "game_type", "game_type_display",
            "release_date", "cover_url", "machines", "genres",
            "prices", "listings", "created_at", "updated_at",
        ]

    def get_prices(self, obj):
        """Retourne uniquement le prix le plus récent par source."""
        seen = {}
        for price in obj.prices.order_by("-scraped_at"):
            if price.source not in seen:
                seen[price.source] = price
        return PriceSerializer(seen.values(), many=True).data
