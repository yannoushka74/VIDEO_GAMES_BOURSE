from rest_framework import serializers

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
    class Meta:
        model = Price
        fields = [
            "id", "source", "price", "old_price", "discount_percent", "currency",
            "cib_price", "new_price", "graded_price", "box_only_price", "manual_only_price",
            "product_url", "product_title", "asin", "image_url",
            "rating", "review_count", "availability", "category", "scraped_at",
        ]


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
    listing_count = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id", "jvc_id", "title", "game_type", "release_date", "cover_url",
            "machines", "genres", "latest_price", "listing_count",
        ]

    def get_latest_price(self, obj):
        price = obj.prices.first()
        if price:
            return {"price": str(price.price), "currency": price.currency, "source": price.source}
        return None

    def get_listing_count(self, obj):
        return obj.listings.count()


class GameDetailSerializer(serializers.ModelSerializer):
    machines = MachineSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    game_type_display = serializers.CharField(source="get_game_type_display", read_only=True)
    prices = PriceSerializer(many=True, read_only=True)
    listings = ListingSerializer(many=True, read_only=True)

    class Meta:
        model = Game
        fields = [
            "id", "jvc_id", "title", "game_type", "game_type_display",
            "release_date", "cover_url", "machines", "genres",
            "prices", "listings", "created_at", "updated_at",
        ]
