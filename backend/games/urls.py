from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("games", views.GameViewSet)
router.register("machines", views.MachineViewSet)
router.register("genres", views.GenreViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", views.api_stats, name="api-stats"),
    path("top/", views.top_expensive, name="top-expensive"),
    path("autocomplete/", views.autocomplete, name="autocomplete"),
    path("opportunities/", views.opportunities, name="opportunities"),
    path("exchange-rates/", views.exchange_rates, name="exchange-rates"),
]
