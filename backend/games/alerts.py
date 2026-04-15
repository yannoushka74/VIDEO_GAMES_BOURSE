"""Logique de déclenchement des alertes prix.

Module découplé du modèle Django : les fonctions prennent des objets
duck-typés pour faciliter les tests unitaires.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .exchange import get_rate


class _AlertLike(Protocol):
    game_id: int
    max_price: object
    currency: str
    is_active: bool

    def allowed_sources(self) -> list[str]: ...


class _ListingLike(Protocol):
    game_id: Optional[int]
    source: str
    currency: str
    current_price: object
    buy_now_price: object


def convert_price(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """Convertit un montant d'une devise à l'autre via les taux cachés.

    Retourne None si le taux n'est pas disponible.
    """
    if from_currency == to_currency:
        return float(amount)
    rate = get_rate(from_currency, to_currency)
    if rate is None:
        return None
    return round(float(amount) * rate, 2)


def effective_listing_price(listing: _ListingLike) -> float:
    """Prix effectif d'un listing : buy_now si présent, sinon current."""
    raw = listing.buy_now_price if listing.buy_now_price is not None else listing.current_price
    return float(raw)


def listing_triggers_alert(alert: _AlertLike, listing: _ListingLike) -> bool:
    """True si le listing doit déclencher l'alerte.

    Conditions :
    - alerte active
    - même jeu (game_id)
    - source du listing dans la liste autorisée
    - prix effectif du listing ≤ max_price (converti dans la devise de l'alerte)
    """
    if not alert.is_active:
        return False
    if listing.game_id != alert.game_id:
        return False
    if listing.source not in alert.allowed_sources():
        return False
    raw_price = effective_listing_price(listing)
    converted = convert_price(raw_price, listing.currency, alert.currency)
    if converted is None:
        return False
    return converted <= float(alert.max_price)


def format_notification_text(alert, listing, listing_price_in_alert_currency: float) -> str:
    """Message Telegram lisible pour une notification d'alerte."""
    game_title = getattr(alert.game, "title", "?")
    return (
        f"🎮 <b>{game_title}</b>\n"
        f"Prix: <b>{listing_price_in_alert_currency} {alert.currency}</b> "
        f"(cible: {alert.max_price} {alert.currency})\n"
        f"Source: {listing.source}\n"
        f"Console: {listing.platform_slug}\n"
        f"Condition: {listing.condition or 'loose'}\n"
        f"<a href=\"{listing.listing_url}\">Voir l'annonce</a>"
    )
