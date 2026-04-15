"""Tests unitaires pour le module de matching annonce → jeu.

Lancement :
    cd backend && python manage.py test scrapers
    cd backend && python -m unittest scrapers.tests     # sans Django

Le module matching.py n'a pas de dépendance Django, les tests sont en
unittest pur avec des fake games (namedtuple).
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Optional

from scrapers.matching import (
    DEFAULT_THRESHOLD,
    clean_tokens,
    detect_condition,
    extract_numbers,
    has_game_indicator,
    is_alien_platform_listing,
    is_likely_accessory,
    match_listing_title,
    normalize,
)


@dataclass
class FakeGame:
    title: str
    title_en: Optional[str] = ""


class NormalizeTest(unittest.TestCase):
    def test_lowercases_and_strips_accents(self):
        self.assertEqual(normalize("PokémonÉdition"), "pokemonedition")

    def test_punctuation_to_space(self):
        self.assertEqual(normalize("Zelda: Ocarina of Time"), "zelda ocarina of time")

    def test_apostrophes_merged(self):
        self.assertEqual(normalize("Yoshi's Story"), "yoshis story")

    def test_trailing_s_rejoined(self):
        # "yoshi s story" (après strip apostrophe) doit redevenir "yoshis story"
        self.assertEqual(normalize("yoshi s story"), "yoshis story")

    def test_empty_and_none_safe(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")  # type: ignore[arg-type]

    def test_multiple_spaces_collapsed(self):
        self.assertEqual(normalize("a   b\t\tc"), "a b c")


class ExtractNumbersTest(unittest.TestCase):
    def test_arabic_numbers(self):
        self.assertEqual(extract_numbers("castlevania 3"), {3})

    def test_roman_numbers(self):
        self.assertEqual(extract_numbers("final fantasy vii"), {7})

    def test_roman_iv_through_x(self):
        self.assertEqual(extract_numbers("rocky iv"), {4})
        self.assertEqual(extract_numbers("star wars ix"), {9})

    def test_multi_numbers(self):
        self.assertEqual(extract_numbers("sonic 2 and sonic 3"), {2, 3})

    def test_out_of_bounds_excluded(self):
        # >= 10000 ignoré (IDs gigantesques)
        self.assertEqual(extract_numbers("item 99999 blob 42"), {42})

    def test_zero_excluded(self):
        self.assertEqual(extract_numbers("level 0 boss"), set())


class CleanTokensTest(unittest.TestCase):
    def test_filters_noise(self):
        # "snes" et "pal" sont du noise, "chrono" et "trigger" sont gardés
        toks = clean_tokens("chrono trigger snes pal")
        self.assertIn("chrono", toks)
        self.assertIn("trigger", toks)
        self.assertNotIn("snes", toks)
        self.assertNotIn("pal", toks)

    def test_short_tokens_filtered(self):
        # "a" < 2 chars
        self.assertNotIn("a", clean_tokens("a chrono"))

    def test_translation_expansion(self):
        # "rubin" (DE) doit ajouter "ruby"
        toks = clean_tokens("pokemon rubin")
        self.assertIn("ruby", toks)
        self.assertIn("rubin", toks)

    def test_fr_to_en_translation(self):
        # "rubis" (FR) → "ruby"
        toks = clean_tokens("pokemon rubis")
        self.assertIn("ruby", toks)


class IsLikelyAccessoryTest(unittest.TestCase):
    def test_console_only_is_accessory(self):
        self.assertTrue(is_likely_accessory("SNES Konsole mit Controller"))

    def test_cable_is_accessory(self):
        self.assertTrue(is_likely_accessory("SCART Kabel für Super Nintendo"))

    def test_bundle_phrase(self):
        self.assertTrue(is_likely_accessory("Spiele Sammlung SNES 10 Stück"))

    def test_quantity_regex(self):
        self.assertTrue(is_likely_accessory("Lot de 5 jeux SNES"))

    def test_strong_token_single_hit(self):
        # "figurine" seul suffit
        self.assertTrue(is_likely_accessory("Mario Figurine en métal"))

    def test_manual_without_complete_context(self):
        # "notice seule" sans contexte complet → accessoire
        self.assertTrue(is_likely_accessory("Zelda Ocarina of Time notice seule"))

    def test_manual_with_complete_context_kept(self):
        # "avec notice" + "complet" → pas accessoire
        self.assertFalse(is_likely_accessory("Zelda Ocarina Time complet avec notice"))

    def test_real_game_listing(self):
        self.assertFalse(is_likely_accessory("Chrono Trigger SNES PAL"))

    def test_empty_title(self):
        self.assertTrue(is_likely_accessory(""))

    def test_jaquette_seule_rejected(self):
        self.assertTrue(is_likely_accessory("Mario 64 jaquette seule"))

    def test_boite_vide_rejected(self):
        self.assertTrue(is_likely_accessory("Zelda boîte vide sans jeu"))

    def test_demo_rejected(self):
        self.assertTrue(is_likely_accessory("Resident Evil demo disc not for resale"))


class IsAlienPlatformTest(unittest.TestCase):
    def test_ps2_is_alien_for_snes(self):
        self.assertTrue(is_alien_platform_listing("Chrono Cross PS2", "snes"))

    def test_snes_target_accepted(self):
        self.assertFalse(is_alien_platform_listing("Chrono Trigger SNES", "snes"))

    def test_listing_mentions_both_consoles(self):
        # Mentionne SNES → override alien PS1
        self.assertFalse(
            is_alien_platform_listing("SNES & PS1 lot Chrono Trigger", "snes")
        )

    def test_xbox_alien(self):
        self.assertTrue(is_alien_platform_listing("Halo Xbox", "n64"))

    def test_dreamcast_listing_for_dreamcast(self):
        self.assertFalse(
            is_alien_platform_listing("Shenmue Dreamcast", "dreamcast")
        )


class HasGameIndicatorTest(unittest.TestCase):
    def test_explicit_console(self):
        self.assertTrue(has_game_indicator("Chrono Trigger Super Nintendo", "snes"))

    def test_generic_word_spiel(self):
        self.assertTrue(has_game_indicator("Chrono Trigger Spiel", "snes"))

    def test_generic_word_cartouche(self):
        self.assertTrue(has_game_indicator("Chrono Trigger cartouche", "snes"))

    def test_no_indicator(self):
        # Pas de mention console ni de mot "jeu"
        self.assertFalse(has_game_indicator("Chrono Trigger poster", "snes"))


class DetectConditionTest(unittest.TestCase):
    def test_graded_wins(self):
        self.assertEqual(
            detect_condition("Chrono Trigger Wata 9.8/10 sealed"), "graded"
        )

    def test_sealed_is_new(self):
        self.assertEqual(
            detect_condition("Chrono Trigger factory sealed"), "new"
        )

    def test_blister_is_new(self):
        self.assertEqual(detect_condition("Zelda sous blister"), "new")

    def test_cib_keywords(self):
        self.assertEqual(
            detect_condition("Chrono Trigger complet avec notice"), "cib"
        )

    def test_loose_explicit(self):
        self.assertEqual(detect_condition("Mario 64 cartouche seule"), "loose")

    def test_default_is_loose(self):
        self.assertEqual(detect_condition("Mario 64"), "loose")

    def test_neuf_sans_blister_is_cib_not_new(self):
        # "neuf sans blister" = ouvert, ne doit pas être classé "new"
        self.assertEqual(
            detect_condition("Chrono Trigger neuf sans blister"), "cib"
        )

    def test_neu_ohne_folie_is_cib(self):
        self.assertEqual(
            detect_condition("Chrono Trigger neu ohne folie"), "cib"
        )

    def test_ebay_brand_new(self):
        self.assertEqual(detect_condition("Chrono Trigger", "Brand New"), "new")

    def test_ebay_new_alone_is_ambiguous(self):
        # "New" seul dans l'API eBay ne doit PAS valoir "new"
        self.assertEqual(detect_condition("Chrono Trigger", "New"), "loose")

    def test_ebay_very_good_is_cib(self):
        self.assertEqual(
            detect_condition("Chrono Trigger", "Very Good"), "cib"
        )

    def test_ebay_acceptable_is_loose(self):
        self.assertEqual(
            detect_condition("Mario 64", "Acceptable"), "loose"
        )


class MatchListingTitleTest(unittest.TestCase):
    def test_exact_match_high_score(self):
        games = [FakeGame(title="Chrono Trigger")]
        game, score = match_listing_title("Chrono Trigger SNES PAL", games)
        self.assertIs(game, games[0])
        self.assertGreaterEqual(score, DEFAULT_THRESHOLD)

    def test_no_match_below_threshold(self):
        games = [FakeGame(title="Super Mario World")]
        game, score = match_listing_title(
            "Final Fantasy VII PS1", games, threshold=70
        )
        self.assertIsNone(game)

    def test_accessory_returns_none(self):
        games = [FakeGame(title="Chrono Trigger")]
        game, score = match_listing_title(
            "SNES Konsole mit Kabel und Controller", games
        )
        self.assertIsNone(game)
        self.assertEqual(score, 0)

    def test_skip_accessories_false_allows_match(self):
        games = [FakeGame(title="Mario 64")]
        # Avec skip_accessories=False, le matching tente quand même
        # (peut match ou pas selon le score)
        _game, _score = match_listing_title(
            "Mario 64 figurine", games, skip_accessories=False
        )
        # Juste vérifier que ça n'explose pas — pas d'assertion forte sur score
        # car il dépend des tokens restants après noise filter

    def test_number_strict_listing_has_game_doesnt(self):
        # "Castlevania III" ne doit PAS matcher "Castlevania" (base sans numéro)
        games = [FakeGame(title="Castlevania")]
        game, score = match_listing_title("Castlevania III Dracula's Curse", games)
        self.assertIsNone(game)

    def test_number_strict_game_has_listing_doesnt(self):
        # Listing "Castlevania" ne doit PAS matcher "Castlevania III"
        games = [FakeGame(title="Castlevania III")]
        game, score = match_listing_title("Castlevania NES PAL", games)
        self.assertIsNone(game)

    def test_number_match_allowed(self):
        games = [FakeGame(title="Final Fantasy VII")]
        game, score = match_listing_title(
            "Final Fantasy VII Complete PS1", games, threshold=60
        )
        self.assertIs(game, games[0])

    def test_title_en_fallback(self):
        # Base FR "Pokemon Rubis", listing EN "Pokemon Ruby" → match via title_en
        games = [FakeGame(title="Pokémon Rubis", title_en="Pokemon Ruby")]
        game, _score = match_listing_title(
            "Pokemon Ruby GBA PAL", games, threshold=60
        )
        self.assertIs(game, games[0])

    def test_de_translation_match(self):
        # Listing "Pokemon Rubin" (DE) doit match "Pokemon Ruby"
        games = [FakeGame(title="Pokemon Ruby")]
        game, _score = match_listing_title(
            "Pokemon Rubin GBA", games, threshold=60
        )
        self.assertIs(game, games[0])

    def test_best_of_multiple_candidates(self):
        games = [
            FakeGame(title="Super Mario World"),
            FakeGame(title="Super Mario Kart"),
            FakeGame(title="Super Mario All-Stars"),
        ]
        game, score = match_listing_title(
            "Super Mario World SNES PAL", games, threshold=70
        )
        self.assertEqual(game.title, "Super Mario World")

    def test_empty_candidates(self):
        game, score = match_listing_title("Chrono Trigger", [])
        self.assertIsNone(game)
        self.assertEqual(score, 0)

    def test_yoshi_apostrophe_bug(self):
        # Bug historique : "Yoshi's Story" vs "yoshi s story"
        games = [FakeGame(title="Yoshi's Story")]
        game, _score = match_listing_title(
            "Yoshis Story N64 PAL", games, threshold=70
        )
        self.assertIs(game, games[0])

    def test_castlevania_exact_with_suite_tolerance(self):
        # Un listing "Castlevania" sans numéro doit match la base "Castlevania"
        games = [FakeGame(title="Castlevania")]
        game, _score = match_listing_title(
            "Castlevania NES PAL boxed", games, threshold=60
        )
        self.assertIs(game, games[0])


class RegressionTest(unittest.TestCase):
    """Tests dérivés de bugs réels corrigés dans l'historique git."""

    def test_shinobi_nes_vs_saturn_x(self):
        # Bug 2026-04-09 : NES Shinobi ne doit pas match Saturn Shinobi X.
        # Ici on simule : même module, contrainte numérique protège déjà.
        # Saturn "Shinobi X" extrait X = 10
        games_saturn = [FakeGame(title="Shinobi X")]
        # Listing NES "Shinobi" (pas de numéro)
        game, _ = match_listing_title(
            "Shinobi NES PAL", games_saturn, threshold=70
        )
        # Via la contrainte stricte sur numéros : listing=∅, game={10} → rejet
        self.assertIsNone(game)

    def test_notice_only_rejected(self):
        # Bug 2026-04-12 : notice-only listings détectés
        games = [FakeGame(title="Zelda Ocarina of Time")]
        game, _ = match_listing_title(
            "Zelda Ocarina of Time notice seule N64", games
        )
        self.assertIsNone(game)

    def test_jaquette_seule_rejected(self):
        games = [FakeGame(title="Super Mario 64")]
        game, _ = match_listing_title(
            "Super Mario 64 jaquette avant N64", games
        )
        self.assertIsNone(game)

    def test_neuf_sans_blister_condition_is_cib(self):
        # Bug 2026-04-12 : "neuf sans blister" = ouvert, pas sealed
        self.assertEqual(
            detect_condition("Chrono Trigger SNES neuf sans blister"), "cib"
        )


if __name__ == "__main__":
    unittest.main()
