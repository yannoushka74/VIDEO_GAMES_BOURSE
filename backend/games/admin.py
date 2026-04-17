from django.contrib import admin

from .models import Alert, AlertNotification, Game, Genre, Machine, Price


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "jvc_id"]
    search_fields = ["name"]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "jvc_id"]
    search_fields = ["name"]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["title", "game_type", "release_date"]
    list_filter = ["game_type", "genres", "machines"]
    search_fields = ["title"]
    filter_horizontal = ["machines", "genres"]


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ["game", "price", "currency", "source", "scraped_at"]
    list_filter = ["source", "currency"]
    search_fields = ["game__title", "product_title"]
    raw_id_fields = ["game"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["game", "max_price", "currency", "sources", "is_active", "created_at"]
    list_filter = ["is_active", "currency"]
    search_fields = ["game__title", "label"]
    raw_id_fields = ["game"]


@admin.register(AlertNotification)
class AlertNotificationAdmin(admin.ModelAdmin):
    list_display = [
        "alert", "listing", "price_at_notification",
        "currency_at_notification", "notified_at",
    ]
    list_filter = ["currency_at_notification"]
    raw_id_fields = ["alert", "listing"]
