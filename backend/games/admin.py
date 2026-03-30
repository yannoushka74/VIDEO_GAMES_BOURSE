from django.contrib import admin

from .models import Game, Genre, Machine, Price


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ["name", "jvc_id", "slug"]
    search_fields = ["name"]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "jvc_id", "slug"]
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
