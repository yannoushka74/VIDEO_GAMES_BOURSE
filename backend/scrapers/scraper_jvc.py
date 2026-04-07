"""
Scraper pour récupérer la liste complète des jeux vidéo depuis l'API jeuxvideo.com (v4)
~45 000 jeux récupérés via pagination
"""

import hmac
import hashlib
import datetime
import urllib.parse
import requests
import csv
import time
import json
import sys

# --- Config API ---
BASE_URL = "https://api.jeuxvideo.com"
PARTNER_KEY = "550c04bf5cb2b"
HMAC_SECRET = b"d84e9e5f191ea4ffc39c22d11c77dd6c"
PER_PAGE = 1000

# Mapping des plateformes (IDs -> noms)
MACHINES = {
    10: "PC", 20: "PS4", 22: "PS5", 30: "Xbox One", 32: "Xbox Series",
    42: "Nintendo Switch 2", 50: "PS3", 60: "Xbox 360", 70: "3DS",
    90: "iOS", 100: "Android", 177539: "Nintendo Switch", 200772: "Steam Deck",
    280: "Mac",
}

# Mapping des genres (IDs -> noms)
GENRES = {
    2000: "Action", 2020: "FPS", 2080: "Plate-Forme", 2100: "Aventure",
    2240: "RPG", 2270: "Action-RPG", 2280: "Roguelike", 2330: "Stratégie",
    2490: "Open World", 2560: "Sport", 2570: "Combat", 2580: "Course",
    2620: "Shooter",
}


def compute_auth(method: str, path: str, query_params: dict = None) -> str:
    """Calcule le header Jvc-Authorization (HMAC-SHA256)."""
    timestamp = datetime.datetime.now().isoformat()
    query_string = ""
    if query_params:
        query_string = urllib.parse.urlencode(sorted(query_params.items()))
    string_to_hash = f"{PARTNER_KEY}\n{timestamp}\n{method}\napi.jeuxvideo.com\n{path}\n{query_string}"
    signature = hmac.new(HMAC_SECRET, string_to_hash.encode(), hashlib.sha256).hexdigest()
    return f"PartnerKey={PARTNER_KEY}, Signature={signature}, Timestamp={timestamp}"


def get_headers(method: str, path: str, query_params: dict = None) -> dict:
    return {
        "Jvc-Authorization": compute_auth(method, path, query_params),
        "User-Agent": "JeuxVideo-Android/338",
        "jvc-app-platform": "Android",
        "jvc-app-version": "338",
        "Content-Type": "application/json",
    }


def fetch_games_page(page: int) -> dict:
    """Récupère une page de jeux."""
    path = "/v4/games"
    params = {"page": page, "perPage": PER_PAGE}
    headers = get_headers("GET", path, params)
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def resolve_names(ids: list, mapping: dict) -> str:
    """Convertit une liste d'IDs en noms lisibles, séparés par ' | '."""
    return " | ".join(mapping.get(i, str(i)) for i in ids)


def main():
    print("=== Scraper jeuxvideo.com - Récupération de tous les jeux ===\n")

    # Première requête pour connaître le total
    print("Récupération de la page 1...")
    data = fetch_games_page(1)
    paging = data["paging"]
    total = paging["totalItemCount"]
    total_pages = paging["totalPageCount"]
    print(f"Total : {total} jeux sur {total_pages} pages\n")

    all_games = []
    all_games.extend(data["items"])
    print(f"  Page 1/{total_pages} - {len(data['items'])} jeux récupérés")

    # Pages suivantes
    for page in range(2, total_pages + 1):
        time.sleep(0.5)  # Respecter le serveur
        try:
            data = fetch_games_page(page)
            items = data["items"]
            all_games.extend(items)
            print(f"  Page {page}/{total_pages} - {len(items)} jeux récupérés (total: {len(all_games)})")
        except requests.exceptions.RequestException as e:
            print(f"  Erreur page {page}: {e}")
            print("  Nouvelle tentative dans 5s...")
            time.sleep(5)
            try:
                data = fetch_games_page(page)
                all_games.extend(data["items"])
                print(f"  Page {page}/{total_pages} - retry OK")
            except Exception as e2:
                print(f"  Échec définitif page {page}: {e2}")

    print(f"\nTotal récupéré : {len(all_games)} jeux")

    # --- Export CSV ---
    csv_path = "jeux_video_complet.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "titre", "plateformes", "genres", "date_sortie", "cover_url"])
        for game in all_games:
            writer.writerow([
                game.get("id", ""),
                game.get("title", ""),
                resolve_names(game.get("machines", []), MACHINES),
                resolve_names(game.get("genres", []), GENRES),
                game.get("releaseDate", ""),
                game.get("coverUrl", ""),
            ])
    print(f"CSV exporté : {csv_path}")

    # --- Export JSON ---
    json_path = "jeux_video_complet.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_games, f, ensure_ascii=False, indent=2)
    print(f"JSON exporté : {json_path}")

    print("\nTerminé !")


if __name__ == "__main__":
    main()
