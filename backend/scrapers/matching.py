"""
Module de matching annonce → jeu en base.

Stratégie :
- Normalisation Unicode (accents, ponctuation).
- Extraction des numéros de suite (arabes ET romains II-X) → contrainte stricte.
- Élimination des mots de bruit (console, état, langue).
- Score rapidfuzz token_sort_ratio (sensible à l'ordre, pénalise les mots en trop).
- Comparaison avec title ET title_en pour gérer FR/EN.
- Seuil par défaut : 75/100.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from rapidfuzz import fuzz

# Mots qui ne discriminent pas un jeu (console, état, packaging, langue)
PLATFORM_NOISE = {
    # Consoles
    "snes", "nes", "n64", "gba", "saturn", "neo", "geo", "aes", "mvs", "cd",
    "nintendo", "sega", "super", "famicom", "supernintendo",
    "console", "konsole", "système", "systeme", "system",
    # Génériques jeu
    "spiel", "game", "jeu", "modul", "module", "cartouche", "cartridge",
    "spiele", "games", "jeux", "modules", "videogame",
    # Packaging / état
    "ovp", "cib", "komplett", "complete", "complet", "boxed", "boite", "box",
    "anleitung", "manual", "originalverpackt", "verpackung", "boxe",
    "neu", "new", "neuf", "neuwertig", "gebraucht", "used", "selten", "rar", "rare",
    "top", "wie", "mint", "scellé", "scelle", "sealed",
    # Langue / région
    "pal", "eur", "europe", "ntsc", "fr", "de", "uk", "ita",
    "français", "francais", "deutsch", "english", "italiano", "espagnol",
    # Liaisons
    "fuer", "fur", "für", "mit", "with", "et", "and", "the", "le", "la",
    "les", "des", "du", "of", "in", "on", "for", "ab", "von", "zu",
    "à", "a", "au", "aux", "an", "ein", "eine", "der", "die", "das",
    # Tarifs / promo
    "preis", "prix", "free", "gratuit", "ohne", "ab1",
    # Édition / version (synonymes peu discriminants)
    "version", "edition", "ed", "edizione", "ausgabe",
}

# Numéros romains → arabes (jusqu'à X)
ROMAN_MAP = {
    "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
}

# Traductions DE/IT → EN/FR pour les titres communs (Pokémon, Harry Potter, etc.)
# Appliquées en EXPANSION : on ajoute les traductions aux tokens du listing
# sans retirer l'original. La granularité est mot par mot.
TOKEN_TRANSLATIONS: dict[str, list[str]] = {
    # Pokémon couleurs (DE / IT → EN)
    "rubin": ["ruby", "rubis"],
    "saphir": ["sapphire"],
    "smaragd": ["emerald", "emeraude"],
    "blattgruen": ["leafgreen", "leaf", "green", "feuille"],
    "blattgruene": ["leafgreen", "leaf", "green", "feuille"],
    "blattgrun": ["leafgreen", "leaf", "green", "feuille"],
    "feuerrot": ["firered", "fire", "red", "rouge", "feu"],
    "feuerrote": ["firered", "fire", "red", "rouge", "feu"],
    "kristall": ["crystal", "cristal"],
    "gelb": ["yellow", "jaune"],
    "rot": ["red", "rouge"],
    "blau": ["blue", "bleu"],
    "gruen": ["green"],
    "grun": ["green"],
    "silber": ["silver", "argent"],
    "schwarz": ["black", "noir"],
    "weiss": ["white", "blanc"],
    "weisse": ["white"],
    "diamant": ["diamond"],
    "perl": ["pearl", "perle"],
    "platin": ["platinum", "platine"],
    "rosso": ["red"],
    "fuoco": ["fire"],
    "verde": ["green"],
    "foglia": ["leaf"],
    "zaffiro": ["sapphire"],
    "rubino": ["ruby"],
    "smeraldo": ["emerald"],
    # Harry Potter
    "stein": ["philosopher", "philosophers", "sorcerers", "pierre"],
    "weisen": ["philosopher", "philosophers", "philosophale"],
    "kammer": ["chamber"],
    "schreckens": ["secrets"],
    "gefangene": ["prisoner", "prisonnier"],
    "gefangener": ["prisoner"],
    "askaban": ["azkaban"],
    "feuerkelch": ["goblet", "fire", "feu"],
    "kelch": ["goblet"],
    "orden": ["order", "ordre"],
    "phoenix": ["phoenix", "phenix"],
    "phönix": ["phoenix"],
    "halbblutprinz": ["half", "blood", "prince"],
    "heiligtuemer": ["hallows"],
    "todes": ["death", "mort"],
    # FR → EN (pour les titres en base FR)
    "rubis": ["ruby", "rubin"],
    "emeraude": ["emerald", "smaragd"],
    "rouge": ["red", "rot"],
    "feu": ["fire"],
    "vert": ["green", "gruen", "grun"],
    "feuille": ["leaf"],
    "bleu": ["blue", "blau"],
    "noir": ["black", "schwarz"],
    "blanc": ["white", "weiss"],
    "argent": ["silver", "silber"],
    "or": ["gold"],
    "perle": ["pearl", "perl"],
    "platine": ["platinum", "platin"],
    # Generic
    "abenteuer": ["adventure", "aventure"],
    "abenteuers": ["adventure"],
    "geheimnis": ["secret"],
    "kampf": ["fight", "battle"],
    "krieger": ["warrior"],
    "ritter": ["knight"],
    "drache": ["dragon"],
    "drachen": ["dragon"],
    "welt": ["world", "monde"],
    "winter": ["winter"],
    "sommer": ["summer"],
    "fluch": ["curse"],
    "schatten": ["shadow", "shadows"],
    "erbe": ["legacy", "heritage"],
    "rache": ["revenge"],
    "ruckkehr": ["return", "retour"],
    "rückkehr": ["return"],
    "team": ["team", "rescue"],
    "donnerblitz": ["thunder", "tonnerre"],
    "ausgabe": ["edition"],
    "edition": ["edition"],
    # 007 / Bond
    "welt ist nicht genug": ["world is not enough"],
    "goldenauge": ["goldeneye"],
    # Movies & franchises GBA / NES
    "baphomets": ["broken", "sword"],
    "haie": ["shark", "sharks"],
    "fische": ["fish", "fishes", "tale"],
    "pinguine": ["penguins"],
    "pinguin": ["penguin"],
    "robinsons": ["robinsons"],
    "triff": ["meet"],
    "duellanten": ["duelist", "duelists"],
    "tag": ["day"],
    "vergessene": ["lost", "forgotten"],
    "vergesse": ["lost", "forgotten"],
    "epoche": ["age"],
    "tier": ["beast"],
    "tiere": ["beasts"],
    "geister": ["ghosts", "spirits"],
    "geist": ["ghost", "spirit"],
    "konig": ["king"],
    "könig": ["king"],
    "konigreich": ["kingdom"],
    "königreich": ["kingdom"],
    "land": ["land"],
    "vor": ["before"],
    "zeit": ["time"],
    "verlorene": ["lost"],
    "verlorenen": ["lost"],
    "zeitalter": ["age"],
    "der": [],  # vide → ne change rien (de est déjà filtré comme noise)
    # IT
    "anniversario": ["anniversary"],
    "edizione": ["edition"],
    "limitata": ["limited"],
    "perduta": ["lost"],
    "perduto": ["lost"],
}

# Patterns indiquant un listing accessoire / bundle / console seule (pas un jeu)
# Match sur le titre normalisé (mots).
# Tokens "FORTS" : un seul hit suffit à classer l'annonce comme accessoire.
# Réservés aux mots qui ne peuvent quasiment jamais apparaître dans un titre de jeu.
ACCESSORY_TOKENS_STRONG = {
    # Médias non-jeu (DVD, BluRay, OST, livres)
    "dvd", "bluray", "vhs", "vinyl", "lp",
    "soundtrack", "ost",
    "buch", "book", "livre", "artbook", "guidebook",
    # Notices / manuels seuls (mots sans ambiguïté)
    "bedienungsanleitung",
    # Jaquettes / inserts (jamais un jeu)
    "jaquette", "insert", "inlay",
    # Pièces / accessoires robot ROB NES
    "spatule",
    # Jouets / collection / cartes
    "lego", "moc", "playmobil", "figurine", "figurines", "amiibo",
    "tcg", "booster", "boosters", "ccg",
    "jigsaw",
    "kappe", "casquette", "mug", "tasse",
    # Hardware
    "konsole", "console", "konsolen",
    "controller", "controllers", "manette", "manettes", "joystick", "pad",
    # Câbles & alim
    "kabel", "verlaengerungskabel", "verlangerungskabel",
    "ladekabel", "ladegerat", "ladegeraet",
    "netzteil", "transformator", "alimentation", "chargeur",
    "adapter", "adaptateur",
    # Mémoire / packs hardware
    "transferpak", "memorypak", "memorypack", "speicherkarte",
    "rumblepak", "rumblepack", "expansionpak", "expansionpack",
    # Audio
    "headset", "casque", "ecouteur", "ecouteurs",
    # Boîtes / housses
    "softbox", "schutzhuelle", "schutzhulle", "carrycase", "transportcase",
    "schlusselanhanger", "schlüsselanhänger", "keychain",
    # Goodies
    "tshirt", "poster", "sticker", "stickers", "portecle",
    # Magazines
    "magazin", "magazine", "zeitschrift",
    # Generic accessoire
    "zubehoer", "zubehör", "accessoire", "accessoires", "accessory",
    # Cartouches vides / repro / non-jeux
    "repro", "reproduction", "shells",
    "imprimante", "3d print", "printed",
    "figurine",
    # "figur" seul (allemand pour figurine, pas dans un titre de jeu)
    "figur",
    # Goodies / non-jeux (single token)
    "phonecard", "poster", "affiche", "badge",
    "coque", "etui",
    "statue",
}

# Tokens "FAIBLES" : isolés, ils ne suffisent pas (peuvent apparaître dans des titres).
# Comptés dans le ratio pour décision.
ACCESSORY_TOKENS_WEAK = {
    "ersatz", "remplacement", "ersatzteil",
    "sammlung", "sammlungen", "konvolut",
    "set", "paket", "bundle", "pack", "lot",
}

# Pour rétro-compat : tous les tokens accessoires (utilisés par le calcul de ratio)
ACCESSORY_TOKENS = ACCESSORY_TOKENS_STRONG | ACCESSORY_TOKENS_WEAK

# Phrases d'accessoires/bundles/non-jeux (matching exact dans le titre normalisé)
ACCESSORY_PHRASES = (
    "neo geo mini",
    "snes mini",
    "nes mini",
    "snes classic",
    "nes classic",
    "n64 mini",
    "cartridge shells",
    "cartridge shell",
    "cable hdmi",
    "hdmi cable",
    "gba sp tasche",
    "gba sp case",
    "gba sp bag",
    "carry case",
    "carrying case",
    "konsole mit",
    "konsole und",
    "console with",
    "pad pro",
    "pro gear",
    "av kabel",
    "av cable",
    "scart kabel",
    "scart cable",
    # Médias non-jeu
    "blu ray",
    "blu-ray",
    "cd audio",
    "motion picture",
    "movie cd",
    "movie dvd",
    "music cd",
    "trading cards",
    "trading card",
    "puzzle pack",
    "jigsaw puzzle",
    # Manuels / notices seules
    "anleitung zu",
    "anleitung fuer",
    "spielanleitung",
    "nur anleitung",
    "only manual",
    "manual only",
    "notice seule",
    "notice pour",
    "notice de ",
    "notice du ",
    "instruction booklet",
    "origspielanleitung",
    "original anleitung",
    "pas de jeu",
    "ohne spiel",
    "no game",
    "sans jeu",
    # Neuf sans blister = ouvert, pas sealed
    "neuf sans blister",
    "neu ohne folie",
    "new without",
    # Jaquettes / boîtes vides / disques seuls
    "jaquette avant",
    "jaquette arriere",
    "jaquette seule",
    "boite vide",
    "boitier vide",
    "boite seule",
    "boitier seul",
    "boite boitier",
    "empty box",
    "box only",
    "nur box",
    "nur ovp",
    "only box",
    "case only",
    "hulle nur",
    "cd seul",
    "disc seul",
    "disk only",
    "disc only",
    "cd only",
    # Accessoires spécifiques
    "super game boy",
    "game boy player",
    "pro action replay",
    "action replay",
    "game genie",
    "game shark",
    # Robot ROB NES (pièces détachées)
    "spatule rob",
    "block rob",
    "block stack up",
    "rob stack",
    "rob gyromite",
    # Goodies / accessoires cosmétiques / non-jeux
    "snap lock",
    "phone card",
    "carte telephonique",
    "porte cle",
    "pin badge",
    "beast kingdom",     # figurines/statues
    "figur statue",
    "figurine statue",
    # Covers / boîtiers de remplacement (pas le jeu)
    "cover and case",
    "case replacement",
    "cover replacement",
    "replacement case",
    "replacement cover",
    "artwork only",
    "cover art only",
    "label only",
    "custom case",
    "custom cover",
    # Manuels FR
    "manuel de",
    "manuel du",
    "manuel d ",
    "notice de",
    "notice du",
    # Démos
    " demo ",
    " demo sega",
    " demo disc",
    " demo disk",
    "not for resale",
    # Étuis / fourreaux
    "fourreau",
    # Rééditions / repros modernes (pas des cartouches officielles d'époque)
    "strictly limited",
    "limited run games",
    "limited run game",
    "lrg games",
    "premium edition games",
    "super rare games",
    "forever physical",
    "retro-bit",
    "retrobit",
    "piko interactive",
    "evercade",
    "fan made",
    "fan-made",
    "homebrew",
    "rom hack",
    "romhack",
    "aftermarket",
    "modern reprint",
    "reedition",
    "rééédition",
    "ré-édition",
    # Produits réimprimés connus
    "turrican anthology",
    "turrican director",
    "turrican directors",
    "turrican 2 se ",
    "turrican 2 special",
    "super turrican 2 se",
    "super turrican 2 special",
    "turrican collection",
    " 30th anniversary",
)

# Phrases indiquant une console DIFFÉRENTE des cibles (PS, Xbox, Wii, etc.)
# Matché en substring sur le titre normalisé.
ALIEN_PLATFORM_PHRASES = (
    "ps2", "ps3", "ps4", "ps5",
    "psp", "psvita", "ps vita", " umd",
    "xbox", "xbox 360", "xbox one",
    "wii u", "wiiu", "wii ", "gamecube", "game cube",
    " ds ", " 3ds", " 2ds", " switch",
    "mega drive", "megadrive", "genesis", "master system", "game gear", "gamegear",
    "game boy color", "gameboy color", "gbc",
    "atari", "jaguar", "lynx", "intellivision",
    "amiga", "amstrad", "c64", "commodore", "spectrum", " msx ",
    "pc engine", "pcengine", "turbografx",
    "android", " ios ",
    "pc cd",
)

# Phrases qui CONFIRMENT la console cible (mapping inverse de PLATFORM_KEYWORDS).
# Si l'une est présente, on ignore les "alien" (le listing peut citer plusieurs consoles).
ACCEPTED_PLATFORM_PHRASES = {
    "snes": ("snes", "super nintendo", "super nes"),
    "nes": ("nes", "nintendo entertainment"),
    "n64": ("n64", "nintendo 64"),
    "gba": ("gba", "game boy advance", "gameboy advance"),
    "saturn": ("saturn", "sega saturn"),
    "neo": ("neo geo aes", "neogeo aes"),  # PAS "neo geo" seul (trop large, matche Pocket/CD/Dreamcast)
    "ps1": ("ps1", "psx", "playstation 1", "ps one", "psone"),
    "dreamcast": ("dreamcast", "sega dreamcast"),
}

# Phrases alien SPÉCIFIQUES par console cible (en plus de ALIEN_PLATFORM_PHRASES)
# Permet de filtrer les sous-variantes (Neo Geo Pocket vs AES, etc.)
ALIEN_PER_PLATFORM = {
    "neo": (
        "dreamcast", "sega dreamcast",
        "neo geo pocket", "neogeo pocket", "neo-geo pocket", "ngpc",
        "neo geo cd", "neogeo cd", "neo-geo cd", "neo geo cdz", "neogeo cdz",
        "neo4all",  # emulateur Dreamcast
        "playstation", "ps2", "ps1", "psx", "sony",
        "imprimante 3d", "3d print",
        # MVS = arcade, les cotes AES (console) sont 10x plus chères
        " mvs", "neo geo mvs", "neogeo mvs", "neo-geo mvs",
        "mv-", "mv1", "mv2", "mv4", "mv6",  # MVS board refs
        "arcade pcb", "pcb board", "jamma",
    ),
    "nes": (
        "gameboy", "game boy", "gba", "gbc",
        " switch", "nintendo switch", "nes edition",
    ),
    "snes": (
        "gameboy", "game boy", "gba", "gbc",
        " switch", "nintendo switch",
    ),
    "n64": (
        "gameboy", "game boy", "gba", "gbc",
        " switch", "nintendo switch",
    ),
    "gba": (
        "gba micro",  # hardware, pas un jeu
    ),
}


def is_alien_platform_listing(title: str, target_platform: str) -> bool:
    """True si le titre mentionne explicitement une console différente de la cible.

    Permet de rejeter "ps2", "xbox", "wii" dans une recherche ciblée sur snes.
    Tolère les listings qui mentionnent AUSSI la console cible.

    Pour Neo Geo, rejette spécifiquement Pocket, CD, Dreamcast, PS2
    car "neo geo" dans le titre matche toutes les variantes.
    """
    norm = " " + normalize(title) + " "

    # D'abord vérifier les aliens spécifiques à cette console
    platform_aliens = ALIEN_PER_PLATFORM.get(target_platform, ())
    if platform_aliens and any(p in norm for p in platform_aliens):
        return True

    accepted = ACCEPTED_PLATFORM_PHRASES.get(target_platform, ())
    # Si la console cible est mentionnée, on accepte sans regarder les alien génériques
    if any(p in norm for p in accepted):
        return False
    # Sinon, si une console étrangère est mentionnée, c'est un alien
    return any(p in norm for p in ALIEN_PLATFORM_PHRASES)


# Mots indiquant "ceci est un jeu vidéo" (en plus de la console)
GAME_INDICATOR_WORDS = (
    " spiel", " spiele", " game", " games", " jeu", " jeux",
    " modul", " module", " modulen", " cartouche", " cartouches",
    " cartridge", " cartridges", " rom",
)


def has_game_indicator(title: str, target_platform: str) -> bool:
    """True si le titre contient un mot qui confirme que c'est un jeu vidéo.

    Critères :
    - Mention explicite de la console cible (snes, gba, super nintendo...)
    - OU mot générique "spiel / game / jeu / modul / cartouche / rom"

    Sans cet indicateur, le listing est probablement un livre/film/jouet/lego
    qui partage juste le nom de la franchise.
    """
    norm = " " + normalize(title) + " "
    accepted = ACCEPTED_PLATFORM_PHRASES.get(target_platform, ())
    if any(p in norm for p in accepted):
        return True
    return any(w in norm for w in GAME_INDICATOR_WORDS)

# Regex pour détecter "N games / N controllers / N spiele / N modules" → bundle
BUNDLE_QUANTITY_RE = re.compile(
    r"\b\d+\s*x?\s*(games?|spiele|jeux|modul[en]?|controllers?|cartouches?|cartridges?|stueck|stuck)\b",
    re.IGNORECASE,
)

# Patterns multi-mots indiquant un bundle / collection
BUNDLE_PHRASES = (
    "ohne spiel",
    "konsole mit",
    "konsole und",
    "console with",
    "console bundle",
    "set complet",
    "set complete",
    "lot de jeux",
    "spiele sammlung",
    "spielesammlung",
    "spiele paket",
    "games collection",
    "games bundle",
    "konvolut",
    "sammlung",
    "with games",
    "with controller",
    "and controller",
    "div. zubehoer",
    "div zubehoer",
    "viel zubehoer",
    "diverses",
    "divers",
)

DEFAULT_THRESHOLD = 70

# --- Détection de condition (loose / cib / new / graded) ---

# Mots-clés indiquant un jeu COMPLET en boîte (CIB)
CIB_KEYWORDS = re.compile(
    r"\b(cib|complet|komplett|complete|vollstandig|vollständig|"
    r"mit ovp|avec boite|avec boîte|in ovp|in box|boxed|"
    r"originalverpackung|originalverpackt|"
    r"mit anleitung|avec notice|with manual|"
    r"big box)\b",
    re.IGNORECASE,
)

# Mots-clés indiquant un jeu NEUF / SCELLÉ
# Note : "new" seul est trop ambigu (= "newly listed" sur eBay), on ne garde
# que les variantes explicites (sealed, blister, factory sealed, brand new).
NEW_KEYWORDS = re.compile(
    r"\b(sealed|scelle|scellé|factory sealed|blister|"
    r"neuf sous|neuf scelle|neuware|brand new|"
    r"sous blister|still sealed|unopened|non ouvert)\b",
    re.IGNORECASE,
)

# Mots-clés indiquant un jeu GRADÉ
GRADED_KEYWORDS = re.compile(
    r"\b(graded|wata|vga|cgc|ukg|\d+\.?\d*\s*/\s*10)\b",
    re.IGNORECASE,
)

# Mots-clés indiquant explicitement LOOSE
LOOSE_KEYWORDS = re.compile(
    r"\b(loose|modul|cartouche|cartridge|cart only|"
    r"nur modul|nur spiel|nur cartridge|game only|"
    r"ohne ovp|sans boite|sans boîte|no box|unboxed)\b",
    re.IGNORECASE,
)


def detect_condition(title: str, ebay_condition: str = "") -> str:
    """Détecte la condition d'un listing à partir du titre et/ou du champ eBay.

    Retourne : 'graded', 'new', 'cib', 'loose'
    Ordre de priorité : graded > new > cib > loose (défaut)
    """
    combined = f"{title} {ebay_condition}"

    if GRADED_KEYWORDS.search(combined):
        return "graded"
    # "neuf sans blister" / "neu ohne folie" = ouvert, pas sealed → cib
    low = combined.lower()
    if "neuf sans" in low or "neu ohne" in low or "new without" in low:
        return "cib"
    if NEW_KEYWORDS.search(combined):
        return "new"
    if CIB_KEYWORDS.search(combined):
        return "cib"
    if LOOSE_KEYWORDS.search(combined):
        return "loose"

    # Mapping conditions eBay API → notre nomenclature
    # "New" seul dans l'API eBay n'est PAS fiable pour les jeux rétro
    # (souvent = "newly listed", pas "sealed"). Seul "Brand New" compte.
    ebay_lower = ebay_condition.lower()
    if "brand new" in ebay_lower:
        return "new"
    if "very good" in ebay_lower or "like new" in ebay_lower:
        return "cib"  # Very Good sur eBay = souvent complet
    if "good" in ebay_lower or "acceptable" in ebay_lower:
        return "loose"  # Good/Acceptable = souvent loose

    # Défaut : loose
    return "loose"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Minuscules, sans accents, espaces normalisés, ponctuation→espace.

    Cas spécial : reconstruction des apostrophes-s perdues lors de la
    décomposition de slugs (ex: "yoshi s story" → "yoshis story",
    "donkey kong country dixie kong s double trouble" → "...kongs double trouble").
    """
    if not text:
        return ""
    text = _strip_accents(text).lower()
    text = re.sub(r"['’`]", "", text)  # apostrophes collées
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Recoller un "s" isolé au mot précédent : "yoshi s story" → "yoshis story"
    text = re.sub(r"(\w{2,})\s+s\b", r"\1s", text)
    return text


def extract_numbers(normalized_text: str) -> set[int]:
    """Extrait tous les numéros (arabes et romains) d'un texte normalisé.

    Limite : 0 < v < 10000 → garde 1080, 2002, 2004 (jeux qui ont ces nums)
    et exclut les IDs gigantesques.
    """
    nums: set[int] = set()
    for n in re.findall(r"\b(\d+)\b", normalized_text):
        try:
            v = int(n)
            if 0 < v < 10000:
                nums.add(v)
        except ValueError:
            pass
    for r, v in ROMAN_MAP.items():
        if re.search(rf"\b{r}\b", normalized_text):
            nums.add(v)
    return nums


def clean_tokens(normalized_text: str) -> list[str]:
    """Tokens utiles : >= 2 caractères et pas dans PLATFORM_NOISE.

    Étend aussi les traductions DE/IT → EN pour matcher les jeux multilingues.
    """
    base = [
        t for t in normalized_text.split()
        if len(t) >= 2 and t not in PLATFORM_NOISE
    ]
    expanded = list(base)
    for t in base:
        for tr in TOKEN_TRANSLATIONS.get(t, ()):
            if tr not in expanded:
                expanded.append(tr)
    return expanded


DESCRIPTION_REPRO_MARKERS = (
    # Repro / reprint explicites
    "reproduction", "repro cartridge", "repro cart", "this is a repro",
    "is a reproduction", "modern reprint", "new reprint",
    # Marques de repro modernes (forme courte = match plus large)
    "strictly limited",
    "limited run",  # marque de reprint (Limited Run Games)
    "premium edition games", "super rare games", "forever physical",
    "retro-bit", "retrobit", "piko interactive", "evercade",
    # Fan / homebrew
    "fan made", "fan-made", "homebrew", "rom hack", "romhack",
    "aftermarket cartridge",
    # Mention française explicite
    "non officiel", "non-officiel",
    "n est pas officiel", "n est pas une cartouche officiel",
    "pas de logo nintendo", "pas de logo super nintendo",
    "cartouche reimprime", "boite reimprime", "réimprimé", "reimprime",
    "retro reedition", "reedition moderne", "ré édition",
    # Édition limitée + sealed dans description
    "edition limitee neuve", "limited edition sealed",
)


def is_likely_accessory(title: str, description: str = "") -> bool:
    """True si le listing semble être un accessoire / bundle / console seule / repro.

    Cas détectés :
    - Phrases bundle ("konsole mit", "spiele sammlung", "lot de jeux"...)
    - Le titre ne contient AUCUN mot autre que des accessoires + noise console
    - Plus de 50% des tokens utiles sont des termes accessoires
    - Si `description` fournie : marqueurs explicites de repro / reprint
    """
    # Description : marqueurs explicites de repro/reprint (priorité haute)
    if description:
        desc_norm = normalize(description)
        if any(m in desc_norm for m in DESCRIPTION_REPRO_MARKERS):
            return True

    norm = normalize(title)
    if not norm:
        return True

    # Phrases bundle prioritaires
    for phrase in BUNDLE_PHRASES:
        if phrase in norm:
            return True

    # Phrases accessoires (cable hdmi, gba sp tasche, neo geo mini, etc.)
    for phrase in ACCESSORY_PHRASES:
        if phrase in norm:
            return True

    # Combo "Special Edition" / "Anniversary" + sealed sur jeu retro = repro moderne
    # Strictly Limited Games, Limited Run Games, etc. vendent des reprints
    # de jeux 1990s comme "Super Turrican 2 SE NEUF SOUS BLISTER".
    # Les vraies cartouches Nintendo officielles d'époque ne sont pratiquement
    # jamais factory-sealed 30 ans après.
    REPRO_EDITION_MARKERS = (
        "special edition", "anniversary edition", "30th anniversary",
        "25th anniversary", "anniversary collection", "directors cut",
        "director s cut", "collectors edition", "collector edition",
        "limited collector",
    )
    SEALED_MARKERS = (
        "sealed", "scelle", "factory sealed", "neuf sous blister",
        "neu ohne folie", "neuware", "sous blister", "still sealed",
        "blister",
    )
    has_edition = any(m in norm for m in REPRO_EDITION_MARKERS)
    has_sealed = any(m in norm for m in SEALED_MARKERS)
    if has_edition and has_sealed:
        return True

    # Pattern "N games / N controllers / N spiele"
    if BUNDLE_QUANTITY_RE.search(norm):
        return True

    tokens = norm.split()
    useful = [t for t in tokens if len(t) >= 2 and t not in PLATFORM_NOISE]
    if not useful:
        return True

    # Token "fort" : 1 seul hit suffit
    if any(t in ACCESSORY_TOKENS_STRONG for t in useful):
        return True

    # Tokens "faibles" : il en faut une proportion significative
    weak_hits = sum(1 for t in useful if t in ACCESSORY_TOKENS_WEAK)
    if weak_hits and weak_hits >= len(useful) * 0.5:
        return True

    # Détection "notice seule" / "manual only" :
    # Si le titre contient "notice" / "anleitung" / "manual" / "booklet"
    # MAIS PAS de contexte "complet" (mit anleitung, avec notice, complete),
    # c'est probablement un manuel vendu séparément.
    manual_words = ("notice", "anleitung", "booklet", "handbuch", "instruction", "manual")
    complete_context = (
        "komplett", "complete", "complet", "cib",
        "mit anleitung", "avec notice", "with manual",
        "mit ovp", "avec boite", "in box", "boxed",
    )
    if any(w in norm for w in manual_words):
        if not any(c in norm for c in complete_context):
            return True

    return False


def _token_overlap(listing_tokens: list[str], game_tokens: list[str]) -> float:
    """Fraction des tokens du jeu présents dans le listing.

    - Exact match prioritaire
    - Fuzzy match 85+ SEULEMENT pour les tokens de 5+ caractères
      (évite rob↔robo, war↔wars, pro↔pros qui matchaient trop fort)
    """
    if not game_tokens:
        return 0.0
    hits = 0
    for gt in game_tokens:
        if gt in listing_tokens:
            hits += 1
            continue
        # Fuzzy uniquement pour tokens >= 5 chars (tolère métroid/metroids)
        if len(gt) >= 5:
            for lt in listing_tokens:
                if len(lt) >= 5 and fuzz.ratio(gt, lt) >= 90:
                    hits += 1
                    break
    return hits / len(game_tokens)


def _score_pair(listing_clean: str, listing_nums: set[int],
                game_clean: str, game_nums: set[int]) -> int:
    """Score de matching entre une annonce nettoyée et un jeu nettoyé.

    Stratégie stricte :
    1. Contrainte numéros de suite (identique à avant)
    2. TOUS les tokens significatifs du jeu doivent être dans le listing
       (exact ou fuzzy 85+ pour les variantes orthographiques)
    3. Score = pourcentage de tokens du jeu trouvés × 100

    Les tokens sont expandés (traductions DE/FR/IT incluses) donc
    "Pokemon Rubin" matche "Pokemon Ruby" via l'expansion rubin→ruby.
    """
    if listing_nums and game_nums:
        if not (listing_nums & game_nums):
            return 0
    elif listing_nums and not game_nums:
        return 0
    elif game_nums and not listing_nums:
        return 0

    if not listing_clean or not game_clean:
        return 0

    listing_tokens = listing_clean.split()
    game_tokens = game_clean.split()

    # Exiger que TOUS les tokens du jeu soient dans le listing (STRICT)
    # Plus de tolérance "1 missing token" : trop permissif (matchait
    # "Zelda Ocarina of Time" à "Zelda Ocarina of Time Special Edition").
    overlap = _token_overlap(listing_tokens, game_tokens)
    if overlap < 1.0:
        return 0

    # Jeux avec très peu de tokens (1-2) : exiger une précision élevée
    # pour éviter "Invader" (1 token) matchant "Space Invaders" (2 tokens listing)
    # Le listing a des mots significatifs en plus → ce n'est pas le bon jeu
    if len(game_tokens) <= 2:
        non_noise = [t for t in listing_tokens if t not in game_tokens]
        # Si le listing a plus de tokens significatifs que le jeu lui-même, rejeter
        if len(non_noise) > len(game_tokens):
            return 0

    # Score basé sur la proportion de tokens du listing qui viennent du jeu
    # Un game_tokens > listing_tokens signifie qu'on a supprimé du bruit
    # du listing (noise tokens) → score plafonné à 100
    precision = min(len(game_tokens) / max(len(listing_tokens), 1), 1.0)
    return int(100 * max(precision, 0.75))


def match_listing_title(
    listing_title: str,
    candidate_games: Iterable,
    threshold: int = DEFAULT_THRESHOLD,
    skip_accessories: bool = True,
):
    """Retourne (game, score) ou (None, 0).

    `candidate_games` est un itérable de Game (déjà filtré sur la console).
    Compare contre `title` ET `title_en` pour chaque jeu.

    Si `skip_accessories=True`, les annonces d'accessoires/bundles renvoient
    immédiatement (None, 0) sans tentative de matching.
    """
    if skip_accessories and is_likely_accessory(listing_title):
        return None, 0

    listing_norm = normalize(listing_title)
    listing_nums = extract_numbers(listing_norm)
    listing_tokens = clean_tokens(listing_norm)
    if not listing_tokens:
        return None, 0
    listing_clean = " ".join(listing_tokens)

    # Collecter TOUS les candidats valides avec leur nombre de tokens
    # pour pouvoir choisir le plus specifique (le plus de tokens matches)
    candidates_scored = []  # [(score, nb_game_tokens, game)]

    for game in candidate_games:
        best_game_score = 0
        best_game_tokens = 0
        for raw_title in (game.title, getattr(game, "title_en", "") or ""):
            if not raw_title:
                continue
            game_norm = normalize(raw_title)
            game_nums = extract_numbers(game_norm)
            game_tokens = clean_tokens(game_norm)
            if not game_tokens:
                continue
            game_clean = " ".join(game_tokens)

            score = _score_pair(listing_clean, listing_nums, game_clean, game_nums)
            if score > best_game_score:
                best_game_score = score
                best_game_tokens = len(game_tokens)

        if best_game_score >= threshold:
            candidates_scored.append((best_game_score, best_game_tokens, game))

    if not candidates_scored:
        return None, 0

    # Trier par (score desc, nb_tokens desc) → prefere le titre le plus specifique
    # Ex: "Space Invaders" (2 tokens) gagne sur "Invader" (1 token) a score egal
    # Ex: "Zelda Ocarina of Time" (4 tokens) gagne sur "Zelda Ocarina of Time [Special Edition]"
    #     car precision plus haute pour le titre court vs listing court
    candidates_scored.sort(key=lambda x: (-x[0], -x[1]))
    score, _, best_game = candidates_scored[0]
    return best_game, score
