# Video Games Bourse

Plateforme web de suivi des cotes de jeux vidéo rétro collector. Focus sur 8 consoles : Neo Geo, NES, SNES, GBA, Saturn, N64, PS1, Dreamcast.

Source de vérité pour le scope : `RETRO_SLUGS` dans `backend/games/views.py`.

## Déploiement production (K3s)

Le projet tourne sur un cluster K3s local exposé via Tailscale.

| Service | URL Tailscale |
|---|---|
| Frontend / API | `https://videogames.tail430f32.ts.net` |
| PostgreSQL (LB) | `vgb-postgres.tail430f32.ts.net:5432` |

- **Namespace** : `videogames`
- **Images** : `vgb-backend:latest`, `vgb-frontend:latest`, `vgb-scraper:latest` (imagePullPolicy: `Never`)
- **DB creds** : user `vgb_user`, password `vgb_password`, db `videogames_bourse`
- **Manifests K8s** : `k8s/{namespace,postgres,backend,frontend,ingress}.yaml`

### CI/CD (GitHub Actions)

Le déploiement est automatisé via **GitHub Actions** sur un **self-hosted runner** (`minix-runner`) installé sur la machine K3s.

| Workflow | Trigger | Actions | Durée |
|---|---|---|---|
| `backend.yml` | push `backend/` sur main | Build `vgb-backend` + `vgb-scraper` → import k3s → migrate → rollout restart | ~2 min |
| `frontend.yml` | push `frontend/` sur main | Build `vgb-frontend` → import k3s → rollout restart | ~40s |

**Flow** : `git push origin main` → GitHub Actions → build → deploy → live

Le runner est un service systemd (`actions.runner.yannoushka74-VIDEO_GAMES_BOURSE.minix-runner.service`) qui démarre au boot.

### Rebuild manuel (si besoin)
```bash
# Backend
echo 'Totoro12345!' | sudo -S docker build -t vgb-backend:latest backend/
echo 'Totoro12345!' | sudo -S sh -c 'docker save vgb-backend:latest | k3s ctr images import -'
kubectl rollout restart deployment vgb-backend -n videogames

# Frontend
echo 'Totoro12345!' | sudo -S docker build -t vgb-frontend:latest frontend/
echo 'Totoro12345!' | sudo -S sh -c 'docker save vgb-frontend:latest | k3s ctr images import -'
kubectl rollout restart deployment vgb-frontend -n videogames

# Scraper (Botasaurus + Chromium)
echo 'Totoro12345!' | sudo -S docker build -t vgb-scraper:latest -f backend/Dockerfile.scraper backend/
echo 'Totoro12345!' | sudo -S sh -c 'docker save vgb-scraper:latest | k3s ctr images import -'
```

### Query DB rapide
```bash
kubectl exec -n videogames deployment/vgb-backend -- python -c "
import psycopg2
conn = psycopg2.connect(host='vgb-postgres.videogames.svc.cluster.local',
                       dbname='videogames_bourse', user='vgb_user', password='vgb_password')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM games_game')
print(cur.fetchone())
"
```

## Frontend pages (`frontend/src/pages/`)

- **HomePage.tsx** — best deals Ricardo/eBay triés par décote vs cote PC. CHF primaire, USD secondaire.
- **GamesPage.tsx** — liste paginée + filtres console/prix/recherche.
- **GameDetailPage.tsx** — détail jeu, historique de cote (`PriceHistoryChart.tsx`), listings marketplace, liens PriceCharting.
- **OpportunitiesPage.tsx** — annonces Ricardo/eBay sous-cotées vs cote PC (alimente `/api/opportunities/`).

Composants : `Navbar`, `GameCard`, `Pagination`, `SearchAutocomplete`, `PriceChartingIcon`, `PriceHistoryChart`.

## Alertes prix (Telegram)

Système de wishlist : être notifié quand une annonce Ricardo/eBay passe sous un prix cible pour un jeu précis.

**Modèles** : `Alert` (game, max_price, currency, sources, label, is_active), `AlertNotification` (dédup `(alert, listing)`).

**API** : `GET/POST/PATCH/DELETE /api/alerts/` (CRUD, pas d'auth — single-user).

**Commande** :
```bash
python manage.py check_alerts                # scan + notif Telegram
python manage.py check_alerts --dry-run      # preview, rien envoyé
python manage.py check_alerts --alert 42     # cibler une alerte
python manage.py check_alerts --window-hours 24
```

Planifier via cron/Airflow toutes les 15 min.

**Config Telegram** : variables d'env `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID`. Sans elles, le scan fonctionne (match + dédup en DB) mais log juste en warning.

**Dédup** : `AlertNotification` a un `UniqueConstraint(alert, listing)` — chaque listing n'est notifié qu'une fois par alerte.

## Tests

Tests unitaires (85 tests total, runnables sans DB ni Django) :

```bash
cd backend && python manage.py test scrapers games
# ou sans Django :
cd backend && python -m unittest scrapers.tests games.tests -v
```

- **`scrapers/tests.py`** (66 tests) — couvre `normalize`, `extract_numbers`, `clean_tokens`, `is_likely_accessory`, `is_alien_platform_listing`, `has_game_indicator`, `detect_condition`, `match_listing_title` + régressions (Shinobi NES↔Saturn X, notice seule, jaquette, "neuf sans blister").
- **`games/tests.py`** (19 tests) — logique des alertes prix : `convert_price`, `effective_listing_price`, `listing_triggers_alert` (avec mocks sur `get_rate`), `format_notification_text`.

## Pièges connus / Gotchas

- **Console matching** : tout match prix doit être strictement filtré sur la console du jeu d'origine. Sinon NES Shinobi → Saturn Shinobi X (bug fixé 2026-04-09, 188 mauvais prix supprimés).
- **JVC IDs consoles** : seuls 340, 360, 430, 370, 210, 420 sont les vraies rétro. Les IDs 40, 150, 160, 170, 180, 220 sont d'autres consoles (WiiU, etc.).
- **PriceCharting PAL only** : pas de fallback NTSC. Conséquence : certains jeux NES/GBA sans fiche `PAL *` sur PriceCharting (ex: 1943, ActRaiser GBA, DKC2/3 GBA) restent sans cote — c'est volontaire.
- **Titres FR vs EN** : JVC en français, PriceCharting en anglais. Utiliser `title_en` (rempli par DAG IGDB) pour la recherche quand dispo.
- **`title_en` est NOT NULL** : utiliser `''` pour vider, pas `NULL`.
- **Scrapers Airflow** : le code de scraping productif est dans le repo `airflow-local-setup` (DAGs), PAS dans ce repo. Les `*_scraper.py` ici sont les versions originales en management commands.
- **Module matching dans `scrapers/`, pas `games/`** : `backend/scrapers/matching.py` (705 lignes). Tout changement impactant doit passer les tests `scrapers.tests` sous peine de régresser le match-rate (référence ~72% sur Ricardo).
- **Frontend `m.slug`** : le filtre machine doit utiliser `m.slug` pas `m.jvc_id`.
- **Filtre PAL par défaut** : `_retro_games_qs()` exclut par défaut `pal_status='not_pal'` ET ne garde que les jeux ayant une preuve PAL (`pal_status='pal'` OR cote PriceCharting OR annonce Ricardo). `?include_unverified=true` désactive le filtre. Sur la page détail (`retrieve`), le filtre est bypassé pour autoriser les liens directs.
- **Ricardo URL** : utiliser `%20` (pas `+`) pour encoder les espaces dans les query Ricardo, sinon résultats vides.

## Dev local (legacy)

Le setup ci-dessous est l'ancien dev local docker-compose. **En prod c'est K3s (voir plus haut).**


## Stack technique

- **Backend** : Django 4.2 + Django REST Framework
- **Frontend** : React 19 + TypeScript + Vite
- **Base de données** : PostgreSQL 16 (Docker, port 5433)
- **Scraping** : Botasaurus (anti-détection, Chrome headless + HTTP requests)
- **Données initiales** : API jeuxvideo.com (v4)

## Structure du projet

```
VIDEO_GAMES_BOURSE/
├── backend/
│   ├── config/                    # Django settings, URLs
│   ├── games/
│   │   ├── models.py              # Game, Genre, Machine, Price, Listing
│   │   ├── serializers.py         # DRF serializers
│   │   ├── views.py               # ViewSets (filtrés sur 6 consoles rétro)
│   │   ├── urls.py                # Router DRF
│   │   ├── admin.py               # Interface admin
│   │   ├── amazon_scraper.py      # Scraper Amazon.fr (Botasaurus @browser)
│   │   ├── galaxus_scraper.py     # Scraper Galaxus.ch (Botasaurus @browser)
│   │   ├── pricecharting_scraper.py  # Scraper PriceCharting (Botasaurus @request)
│   │   ├── ricardo_scraper.py     # Scraper Ricardo.ch (Botasaurus @browser)
│   │   └── management/commands/
│   │       ├── import_games.py    # Import JSON jeuxvideo.com → PostgreSQL
│   │       ├── scrape_prices.py   # Scraper prix (Amazon, Galaxus, PriceCharting)
│   │       └── scrape_ricardo.py  # Scraper enchères Ricardo
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.ts                 # Client API
│   │   ├── types.ts               # Interfaces TypeScript
│   │   ├── App.tsx                # Routes
│   │   ├── index.css              # Styles (dark theme)
│   │   ├── components/            # Navbar, GameCard, Pagination, SearchAutocomplete, PriceChartingIcon
│   │   └── pages/                 # HomePage, GamesPage, GameDetailPage
│   └── vite.config.ts
├── data/                          # Données scrappées (gitignored)
│   ├── jeux_video_complet.json    # 45k jeux bruts jeuxvideo.com
│   ├── mappings.json              # ID → nom genres/machines
│   └── scraper_jvc.py             # Scraper initial jeuxvideo.com
├── docker-compose.yml
└── CLAUDE.md
```

## Consoles ciblées

| Plateforme | Slug |
|-----------|------|
| Neo Geo | neo |
| NES | nes |
| SNES | snes |
| GBA | gba |
| Saturn | saturn |
| N64 | n64 |
| PlayStation 1 | ps1 |
| Dreamcast | dreamcast |

PS1 et Dreamcast ont été ajoutés après la v1 initiale. Toute nouvelle console doit être ajoutée dans `RETRO_SLUGS` (`backend/games/views.py`) et dans `SLUG_TO_PC_URL` (mapping PriceCharting) ainsi que dans `ACCEPTED_PLATFORM_PHRASES` de `scrapers/matching.py`.

## Lancement

### 1. PostgreSQL
```bash
docker compose up -d
```

### 2. Backend
```bash
source venv/bin/activate
cd backend
python manage.py migrate
python manage.py import_games ../data/jeux_video_complet.json ../data/mappings.json
python manage.py runserver
```

### 3. Frontend
```bash
cd frontend
npm install --cache /tmp/npm-cache-vgb
npm run dev
```

## Sources de données actives

**Actives en prod** :
1. **jeuxvideo.com (API v4)** — catalogue initial des jeux (titres FR, machines, genres). Scraper dans `backend/scrapers/scraper_jvc.py`.
2. **IGDB** — `title_en` + `pal_status` via DAG Airflow `igdb_pal_status` (hors de ce repo, dans `airflow-local-setup`).
3. **PriceCharting** — cotes collector (loose/CIB/neuf/gradé/boîte seule/manuel seul), **PAL only**. Mode `@request`, ~1.5s/jeu.
   ```bash
   python manage.py scrape_prices --source pricecharting --platform snes,nes,n64,neo,gba,saturn,ps1,dreamcast --all --delay 1
   ```
4. **Ricardo.ch** — enchères en cours (CHF).
   ```bash
   python manage.py scrape_ricardo --platform snes
   python manage.py scrape_ricardo                    # toutes les consoles
   python manage.py scrape_ricardo_targeted           # ciblage jeux de valeur
   ```
5. **eBay** — listings marketplace via API eBay (OAuth token caché). Filtre JP/NTSC (cotes PC sont PAL only).
   ```bash
   python manage.py scrape_ebay_listings --platform snes
   ```

**Legacy / désactivés** (code présent dans le repo mais plus alimentés en prod) :
- Amazon (`scrapers/amazon.py`), Galaxus (`scrapers/galaxus.py`), LeBonCoin (`scrapers/leboncoin.py`).
- Les enums `Price.Source` et `Listing.Source` contiennent encore ces valeurs pour compat des données historiques.

## API Endpoints

| URL | Description |
|-----|-------------|
| `GET /api/games/` | Liste paginée — filtrée PAL-vérifié par défaut |
| `GET /api/games/?include_unverified=true` | Tous les jeux (y compris non vérifiés PAL) |
| `GET /api/games/?search=chrono` | Recherche par titre |
| `GET /api/games/?machine=snes` | Filtrer par console (slug) |
| `GET /api/games/?ordering=-latest_loose_price` | Tri par prix (loose PriceCharting) |
| `GET /api/games/?price_min=50&price_max=300` | Filtre par fourchette de prix |
| `GET /api/games/?has_price=true` | Uniquement jeux avec cote PriceCharting |
| `GET /api/games/:id/` | Détail + prix + enchères (bypass filtre PAL) |
| `GET /api/games/:id/price-history/` | Historique chronologique des cotes scrapées |
| `GET /api/opportunities/?min_discount=20&platform=snes` | Annonces Ricardo sous la cote PriceCharting |
| `GET /api/machines/` | 6 consoles rétro |
| `GET /api/genres/` | Genres |
| `GET /api/stats/` | Compteurs (`games_count` PAL vérifié + `games_count_total`) |
| `GET /api/autocomplete/?q=chr` | Autocomplétion recherche |
| `GET /api/top/?platform=snes` | Top 200 jeux les plus chers |
| `GET /api/exchange-rates/` | Taux de change cachés 24h (via Frankfurter.app) — utilisé par le front pour afficher CHF/EUR/USD |

## Modèles Django

- **Game** : jvc_id, title, **title_en**, **pal_status** (`unknown`/`pal`/`not_pal`, populé via DAG `igdb_pal_status`), game_type, release_date, cover_url + M2M Machine/Genre
- **Machine** : jvc_id, name, slug
- **Genre** : jvc_id, name, slug
- **Price** : game (FK), source, price, cib_price, new_price, graded_price, box_only_price, manual_only_price, old_price, discount_percent, rating, review_count, asin, availability, category, scraped_at (mode append-only → historique conservé)
- **Listing** : game (FK nullable), source, title, listing_url, current_price, buy_now_price, bid_count, ends_at, region, platform_slug

## Module matching annonces (`backend/scrapers/matching.py`)

Module commun utilisé par `scrape_ricardo` (et par `rematch_listings`) pour rattacher une annonce marketplace à un jeu en base. Stratégie :

- **Normalisation Unicode** (sans accents, ponctuation→espace, lowercase)
- **Extraction des numéros** (arabes 1-9999 + romains II-X) avec **vérification stricte** : un listing avec "3" ne peut PAS matcher un jeu sans "3" (et inversement)
- **`PLATFORM_NOISE`** : ~80 mots filtrés (consoles, état, packaging, langues, mots de liaison FR/DE/EN/IT)
- **`TOKEN_TRANSLATIONS`** : ~60 entrées DE/IT/FR ↔ EN bidirectionnel (Pokémon couleurs, Harry Potter, etc.)
- **`is_likely_accessory()`** : détecte les bundles/console seule/manettes/câbles via `ACCESSORY_TOKENS`, `BUNDLE_PHRASES` et `BUNDLE_QUANTITY_RE` (regex `\d+ games?/spiele/controllers?`)
- **Score combiné** rapidfuzz : `0.5×token_set_ratio + 0.3×token_sort_ratio + 0.2×partial_ratio`
- **Comparaison** sur `title` ET `title_en` (le meilleur des deux)
- **Seuil** par défaut : **70/100**

Résultat actuel sur Ricardo : **72% des listings non-accessoires matchés** (vs 51% avec l'ancien matching set-intersection).

## Commande management `rematch_listings`

Retraite le matching annonce → jeu sur les Listings existants sans re-scraper.

```bash
python manage.py rematch_listings --source ricardo            # apply
python manage.py rematch_listings --dry-run                   # preview
python manage.py rematch_listings --threshold 65              # plus permissif
python manage.py rematch_listings --platform snes             # une seule console
```

Affiche un bilan : matchés AVANT/APRÈS, conservés, nouveaux matchs, matchs changés/perdus, exclusion accessoires.

## Conventions

- Backend : Python, Django conventions
- Frontend : TypeScript strict, composants fonctionnels React, CSS vanilla
- UI : Français
- Code : Anglais
- Scraping : Botasaurus (`@request` quand possible, `@browser` sinon), parallélisme configurable

## Configuration

- **PostgreSQL** : DB `videogames_bourse`, user `vgb_user`, password `vgb_password`, port `5433`
- **CORS** : `localhost:5173`
- **Vite proxy** : `/api` → `http://localhost:8000`
