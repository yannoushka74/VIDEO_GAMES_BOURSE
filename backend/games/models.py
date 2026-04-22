from django.db import models


class Machine(models.Model):
    """Plateforme de jeu (PC, PS5, Switch, etc.)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Genre(models.Model):
    """Genre de jeu (RPG, FPS, Action, etc.)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Game(models.Model):
    """Jeu vidéo."""

    class GameType(models.IntegerChoices):
        SERIE = 1, "Série"
        COMPILATION = 2, "Compilation"
        MASTERFICHE = 4, "Masterfiche"
        JEU = 9, "Jeu"
        FICHE_GENERIQUE = 49, "Fiche de jeu générique"

    class PalStatus(models.TextChoices):
        UNKNOWN = "unknown", "Inconnu"
        PAL = "pal", "Sorti en PAL"
        NOT_PAL = "not_pal", "Pas de version PAL"

    pricecharting_url = models.URLField(
        max_length=500, unique=True, null=True, blank=True,
        help_text="URL produit PriceCharting (identifiant catalogue primaire)",
    )
    title = models.CharField(max_length=500, db_index=True)
    title_en = models.CharField(max_length=500, blank=True, help_text="Titre anglais (PriceCharting)")
    game_type = models.IntegerField(choices=GameType.choices, default=GameType.JEU)
    release_date = models.CharField(max_length=100, blank=True)
    cover_url = models.URLField(max_length=500, blank=True)
    pal_status = models.CharField(
        max_length=10,
        choices=PalStatus.choices,
        default=PalStatus.UNKNOWN,
        db_index=True,
        help_text="Statut PAL déterminé via IGDB release_dates",
    )

    machines = models.ManyToManyField(Machine, related_name="games", blank=True)
    genres = models.ManyToManyField(Genre, related_name="games", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Price(models.Model):
    """Prix d'un jeu vidéo scraped depuis une source externe."""

    class Source(models.TextChoices):
        AMAZON = "amazon", "Amazon"
        GALAXUS = "galaxus", "Galaxus"
        PRICECHARTING = "pricecharting", "PriceCharting"
        EBAY = "ebay", "eBay"
        FNAC = "fnac", "Fnac"
        MICROMANIA = "micromania", "Micromania"
        STEAM = "steam", "Steam"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="prices")
    source = models.CharField(max_length=20, choices=Source.choices)

    # Prix principal (loose pour PriceCharting, prix actuel pour Amazon/Galaxus)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percent = models.IntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")

    # Prix collector (PriceCharting)
    cib_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Complet en boîte")
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Neuf scellé")
    graded_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Gradé WATA/VGA")
    box_only_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Boîte seule")
    manual_only_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Manuel seul")

    # Infos produit
    product_url = models.URLField(max_length=500, blank=True)
    product_title = models.CharField(max_length=500, blank=True)
    asin = models.CharField(max_length=20, blank=True, help_text="Identifiant Amazon")
    image_url = models.URLField(max_length=500, blank=True)

    # Avis
    rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    review_count = models.IntegerField(null=True, blank=True)

    # Disponibilité
    availability = models.CharField(max_length=200, blank=True)

    # Catégorie Amazon (pour valider que c'est bien un jeu)
    category = models.CharField(max_length=300, blank=True)

    # Région (PAL/NTSC pour distinguer les cotes PC)
    region = models.CharField(
        max_length=10, blank=True, default="",
        help_text="pal, ntsc, ou '' pour les sources sans distinction",
    )

    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at"]
        indexes = [
            models.Index(fields=["game", "source", "-scraped_at"]),
        ]

    def __str__(self):
        return f"{self.game.title} - {self.price} {self.currency} ({self.source})"


class Listing(models.Model):
    """Enchère ou annonce en cours sur une marketplace (Ricardo, eBay, etc.)."""

    class Source(models.TextChoices):
        RICARDO = "ricardo", "Ricardo"
        EBAY = "ebay", "eBay"
        LEBONCOIN = "leboncoin", "LeBonCoin"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="listings", null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    platform_slug = models.SlugField(max_length=20, help_text="Console: snes, nes, n64, etc.")

    # Annonce
    title = models.CharField(max_length=500)
    listing_url = models.URLField(max_length=500)
    image_url = models.URLField(max_length=500, blank=True)

    # Prix
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    buy_now_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="CHF")

    # Enchère
    bid_count = models.IntegerField(default=0)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Condition & Région
    condition = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=10, blank=True, help_text="PAL, NTSC, JP")

    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ends_at"]
        indexes = [
            models.Index(fields=["source", "platform_slug"]),
            models.Index(fields=["game", "source"]),
        ]

    def __str__(self):
        return f"{self.title[:50]} - {self.current_price} {self.currency} ({self.source})"


class Alert(models.Model):
    """Watch utilisateur : notifier si une annonce pour un jeu passe sous un prix cible."""

    class Currency(models.TextChoices):
        CHF = "CHF", "CHF"
        EUR = "EUR", "EUR"
        USD = "USD", "USD"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="alerts")
    max_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.CHF)
    sources = models.CharField(
        max_length=100,
        default="ricardo,ebay",
        help_text="Sources autorisées séparées par virgule (ricardo,ebay,leboncoin)",
    )
    label = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["game", "is_active"]),
        ]

    def __str__(self):
        return f"{self.game.title} <= {self.max_price} {self.currency}"

    def allowed_sources(self) -> list[str]:
        return [s.strip() for s in (self.sources or "").split(",") if s.strip()]


class AlertNotification(models.Model):
    """Trace d'une notification envoyée. Sert à dédupliquer."""

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="notifications")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="alert_notifications")
    price_at_notification = models.DecimalField(max_digits=10, decimal_places=2)
    currency_at_notification = models.CharField(max_length=3)
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-notified_at"]
        constraints = [
            models.UniqueConstraint(fields=["alert", "listing"], name="uniq_alert_listing"),
        ]

    def __str__(self):
        return f"{self.alert} ← {self.listing}"
