# Video Games Bourse

Plateforme web de suivi des cotes de jeux vidéo rétro collector. Focus sur 6 consoles : Neo Geo, NES, SNES, GBA, Saturn, N64 (~3 282 jeux).

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

| Plateforme | Slug | Jeux | Cote marché |
|-----------|------|------|-------------|
| Neo Geo | neo | 134 | 500€ – 13 000€ |
| NES | nes | 762 | 300€ – 5 000€ |
| SNES | snes | 821 | 200€ – 3 000€ |
| GBA | gba | 1 014 | 100€ – 1 500€ |
| Saturn | saturn | 419 | 200€ – 1 000€ |
| N64 | n64 | 347 | 150€ – 500€ |

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

## Sources de prix

### PriceCharting (cotes collector, USD)
```bash
python manage.py scrape_prices --source pricecharting --platform snes --limit 100
python manage.py scrape_prices --source pricecharting --platform snes,nes,n64,neo,gba,saturn --all --delay 1
```
Mode `@request` (pas de Chrome, ~1.5s/jeu). Retourne : loose, CIB, neuf, gradé, boîte seule, manuel seul.

### Amazon (prix neuf, EUR)
```bash
python manage.py scrape_prices --source amazon --platform snes --limit 50 --parallel 5
```
Mode `@browser` (Chrome headless, ~6s/jeu).

### Galaxus (prix neuf, CHF)
```bash
python manage.py scrape_prices --source galaxus --platform snes --limit 50 --parallel 5
```

### Ricardo (enchères en cours, CHF)
```bash
python manage.py scrape_ricardo --platform snes
python manage.py scrape_ricardo  # toutes les consoles
```

## API Endpoints

| URL | Description |
|-----|-------------|
| `GET /api/games/` | Liste paginée (filtrée sur 6 consoles rétro) |
| `GET /api/games/?search=chrono` | Recherche par titre |
| `GET /api/games/?machine=snes` | Filtrer par console (slug) |
| `GET /api/games/:id/` | Détail + prix + enchères |
| `GET /api/machines/` | 6 consoles rétro |
| `GET /api/genres/` | Genres |
| `GET /api/stats/` | Compteurs |
| `GET /api/autocomplete/?q=chr` | Autocomplétion recherche |

## Modèles Django

- **Game** : jvc_id, title, game_type, release_date, cover_url + M2M Machine/Genre
- **Machine** : jvc_id, name, slug
- **Genre** : jvc_id, name, slug
- **Price** : game (FK), source, price, cib_price, new_price, graded_price, box_only_price, manual_only_price, old_price, discount_percent, rating, review_count, asin, availability, category
- **Listing** : game (FK nullable), source, title, listing_url, current_price, buy_now_price, bid_count, ends_at, platform_slug

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
