"""Tests unitaires pour la logique d'alertes prix.

Lancement :
    cd backend && python manage.py test games
    cd backend && python -m unittest games.tests

Les tests sont en unittest pur : ils patchent `games.alerts.get_rate`
pour éviter les appels réseau et utilisent des fake objects duck-typés
pour Alert/Listing (pas de DB).
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from games.alerts import (
    convert_price,
    effective_listing_price,
    format_notification_text,
    listing_triggers_alert,
)


@dataclass
class FakeGame:
    id: int = 1
    title: str = "Chrono Trigger"
    cover_url: str = ""


@dataclass
class FakeAlert:
    game_id: int
    max_price: Decimal
    currency: str = "CHF"
    is_active: bool = True
    sources: str = "ricardo,ebay"
    game: Optional[FakeGame] = None

    def allowed_sources(self) -> list[str]:
        return [s.strip() for s in (self.sources or "").split(",") if s.strip()]


@dataclass
class FakeListing:
    game_id: Optional[int]
    source: str
    current_price: Decimal
    currency: str = "CHF"
    buy_now_price: Optional[Decimal] = None
    platform_slug: str = "snes"
    listing_url: str = "https://example.com/listing/1"
    condition: str = "loose"


FIXED_RATES = {
    ("USD", "CHF"): 0.80,
    ("CHF", "USD"): 1.25,
    ("EUR", "CHF"): 0.95,
    ("CHF", "EUR"): 1.05,
    ("USD", "EUR"): 0.86,
    ("EUR", "USD"): 1.16,
}


def _fake_rate(from_cur, to_cur):
    return FIXED_RATES.get((from_cur, to_cur))


class ConvertPriceTest(unittest.TestCase):
    def test_same_currency_identity(self):
        self.assertEqual(convert_price(100, "CHF", "CHF"), 100.0)

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_eur_to_chf(self, _m):
        self.assertEqual(convert_price(100, "EUR", "CHF"), 95.0)

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_chf_to_usd(self, _m):
        self.assertEqual(convert_price(100, "CHF", "USD"), 125.0)

    @patch("games.alerts.get_rate", return_value=None)
    def test_rate_unavailable_returns_none(self, _m):
        self.assertIsNone(convert_price(100, "EUR", "CHF"))


class EffectiveListingPriceTest(unittest.TestCase):
    def test_buy_now_wins(self):
        l = FakeListing(
            game_id=1, source="ebay",
            current_price=Decimal("100"),
            buy_now_price=Decimal("80"),
        )
        self.assertEqual(effective_listing_price(l), 80.0)

    def test_falls_back_to_current(self):
        l = FakeListing(game_id=1, source="ebay", current_price=Decimal("100"))
        self.assertEqual(effective_listing_price(l), 100.0)


class ListingTriggersAlertTest(unittest.TestCase):
    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_triggers_when_price_below(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("80"), currency="CHF",
        )
        self.assertTrue(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_equal_to_max_triggers(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("100"), currency="CHF",
        )
        self.assertTrue(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_does_not_trigger_when_above(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("150"), currency="CHF",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_inactive_alert_never_triggers(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), is_active=False)
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("50"), currency="CHF",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_different_game_never_triggers(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"))
        listing = FakeListing(
            game_id=2, source="ricardo",
            current_price=Decimal("50"), currency="CHF",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_source_not_allowed(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), sources="ricardo")
        listing = FakeListing(
            game_id=1, source="ebay",
            current_price=Decimal("50"), currency="CHF",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_eur_alert_chf_listing_above(self, _m):
        # 100 CHF → 105 EUR > 100 EUR → pas de trigger
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="EUR")
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("100"), currency="CHF",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_usd_listing_chf_alert_below(self, _m):
        # 100 USD → 80 CHF ≤ 100 CHF → trigger
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ebay",
            current_price=Decimal("100"), currency="USD",
        )
        self.assertTrue(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_buy_now_price_used(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ebay",
            current_price=Decimal("200"),
            buy_now_price=Decimal("90"),
            currency="CHF",
        )
        self.assertTrue(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", return_value=None)
    def test_rate_unavailable_does_not_trigger(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"), currency="CHF")
        listing = FakeListing(
            game_id=1, source="ebay",
            current_price=Decimal("50"), currency="USD",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_leboncoin_not_allowed_by_default(self, _m):
        alert = FakeAlert(game_id=1, max_price=Decimal("100"))
        listing = FakeListing(
            game_id=1, source="leboncoin",
            current_price=Decimal("50"), currency="EUR",
        )
        self.assertFalse(listing_triggers_alert(alert, listing))

    @patch("games.alerts.get_rate", side_effect=_fake_rate)
    def test_leboncoin_allowed_when_in_sources(self, _m):
        alert = FakeAlert(
            game_id=1, max_price=Decimal("100"), sources="ricardo,leboncoin"
        )
        listing = FakeListing(
            game_id=1, source="leboncoin",
            current_price=Decimal("50"), currency="EUR",
        )
        # 50 EUR → 47.5 CHF ≤ 100 → trigger
        self.assertTrue(listing_triggers_alert(alert, listing))


class FormatNotificationTest(unittest.TestCase):
    def test_contains_key_fields(self):
        game = FakeGame(title="Chrono Trigger")
        alert = FakeAlert(
            game_id=1, max_price=Decimal("120"), currency="CHF", game=game
        )
        listing = FakeListing(
            game_id=1, source="ricardo",
            current_price=Decimal("85"), currency="CHF",
            platform_slug="snes", condition="cib",
            listing_url="https://ricardo.ch/xyz",
        )
        text = format_notification_text(alert, listing, 85.0)
        self.assertIn("Chrono Trigger", text)
        self.assertIn("85", text)
        self.assertIn("120", text)
        self.assertIn("CHF", text)
        self.assertIn("snes", text)
        self.assertIn("cib", text)
        self.assertIn("ricardo", text)
        self.assertIn("ricardo.ch/xyz", text)


if __name__ == "__main__":
    unittest.main()
