#!/usr/bin/env python3
"""Interface web de labellisation rapide pour un dataset N classes.

Détecte automatiquement les classes depuis les sous-dossiers du dataset.
Raccourcis clavier : 1..N = classes, d = delete, → next, ← prev.

Usage :
    python ml/label_web.py --dataset ../dataset --port 8080
    python ml/label_web.py --dataset ../console_dataset --port 8081
"""

from __future__ import annotations

import argparse
import shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CLASSES = []  # set dynamically


class LabelServer(BaseHTTPRequestHandler):
    dataset = None  # Path — set below
    classes = []    # list of class names

    def _list_images(self):
        """Liste toutes les images du dataset avec leur classe actuelle."""
        imgs = []
        for cls in self.classes:
            cls_dir = self.dataset / cls
            if cls_dir.exists():
                for p in sorted(cls_dir.glob("*.jpg")):
                    imgs.append((cls, p.name))
        return imgs

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self._render_index(int(params.get("i", [0])[0]))
        elif path.startswith("/img/"):
            self._serve_image(path[5:])
        elif path == "/label":
            idx = int(params["i"][0])
            new_cls = params["cls"][0]
            self._relabel(idx, new_cls)
        elif path == "/delete":
            idx = int(params["i"][0])
            self._delete(idx)
        else:
            self.send_error(404)

    def _serve_image(self, rel_path):
        full = self.dataset / rel_path
        if not full.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(full.read_bytes())

    def _relabel(self, idx, new_cls):
        imgs = self._list_images()
        if idx < 0 or idx >= len(imgs):
            self._redirect("/?i=0")
            return
        old_cls, name = imgs[idx]
        if new_cls != old_cls and new_cls in self.classes:
            src = self.dataset / old_cls / name
            dst = self.dataset / new_cls / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        next_idx = idx + 1 if new_cls == old_cls else idx
        self._redirect(f"/?i={next_idx}")

    def _delete(self, idx):
        imgs = self._list_images()
        if idx < 0 or idx >= len(imgs):
            self._redirect("/?i=0")
            return
        cls, name = imgs[idx]
        (self.dataset / cls / name).unlink()
        self._redirect(f"/?i={idx}")  # garde l'index car on a retiré cette image

    def _redirect(self, url):
        self.send_response(303)
        self.send_header("Location", url)
        self.end_headers()

    def _render_index(self, idx):
        imgs = self._list_images()
        total = len(imgs)
        if total == 0:
            self._html("Dataset vide", "<p>Aucune image trouvée.</p>")
            return
        if idx >= total:
            idx = total - 1
        if idx < 0:
            idx = 0

        cls, name = imgs[idx]
        counts = {c: sum(1 for cc, _ in imgs if cc == c) for c in self.classes}
        counts_str = " · ".join(f"{c}: {n}" for c, n in counts.items())

        # Générer les boutons dynamiquement pour N classes
        buttons_html = ""
        shortcut_js = ""
        for i, c in enumerate(self.classes, 1):
            current_cls_marker = "btn-current" if cls == c else ""
            buttons_html += (
                f'<a class="btn-class {current_cls_marker}" '
                f'href="/label?i={idx}&cls={c}">{c.upper()} ({i})</a>\n'
            )
            shortcut_js += (
                f"  if (e.key === '{i}') window.location = '/label?i={idx}&cls={c}';\n"
            )

        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Label {idx+1}/{total}</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; margin: 0; padding: 20px; text-align: center; }}
  h1 {{ margin: 0 0 8px 0; font-size: 18px; }}
  .counts {{ color: #888; font-size: 14px; margin-bottom: 20px; }}
  .img-wrap {{ display: inline-block; background: #222; padding: 10px; border-radius: 4px; }}
  img {{ max-width: 500px; max-height: 500px; display: block; image-rendering: pixelated; }}
  .current {{ color: #4CAF50; font-weight: bold; font-size: 14px; margin: 10px 0; }}
  .current.wrong {{ color: #ff9800; }}
  .buttons {{ margin: 20px 0; }}
  .buttons button, .buttons a {{
    font-size: 16px; padding: 12px 20px; margin: 0 8px;
    border: 2px solid #555; background: #222; color: #eee;
    border-radius: 4px; cursor: pointer; text-decoration: none;
    display: inline-block; min-width: 100px;
  }}
  .btn-class {{ border-color: #4CAF50; }}
  .btn-delete {{ border-color: #f44336; }}
  .btn-current {{ background: #555; border-color: #fff; }}
  .nav {{ margin-top: 20px; }}
  .nav a {{ margin: 0 20px; color: #888; text-decoration: none; }}
  .help {{ color: #888; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>
  <h1>Label {idx+1}/{total}</h1>
  <div class="counts">{counts_str}</div>
  <div class="img-wrap">
    <img src="/img/{cls}/{name}" alt="{name}">
  </div>
  <div class="current">Classe actuelle : <b>{cls}</b></div>
  <div class="buttons">
    {buttons_html}
    <a class="btn-delete" href="/delete?i={idx}">Delete (d)</a>
  </div>
  <div class="nav">
    <a href="/?i={max(0, idx-1)}">← Précédent</a>
    <a href="/?i={idx+1}">Suivant →</a>
  </div>
  <div class="help">Raccourcis : {" · ".join(f"{i+1}={c}" for i, c in enumerate(self.classes))} · d=delete · ←/→ nav</div>
<script>
document.addEventListener('keydown', (e) => {{
{shortcut_js}
  if (e.key === 'd') window.location = '/delete?i={idx}';
  else if (e.key === 'ArrowRight') window.location = '/?i={idx+1}';
  else if (e.key === 'ArrowLeft') window.location = '/?i={max(0, idx-1)}';
}});
</script>
</body>
</html>
"""
        self._html(f"Label {idx+1}/{total}", html)

    def _html(self, title, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # silent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../dataset")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    LabelServer.dataset = Path(args.dataset).resolve()
    # Détection auto des classes (sous-dossiers)
    LabelServer.classes = sorted([d.name for d in LabelServer.dataset.iterdir() if d.is_dir()])
    if not LabelServer.classes:
        print(f"Aucune classe trouvée dans {LabelServer.dataset}")
        return
    print(f"Classes détectées : {LabelServer.classes}")
    server = HTTPServer((args.host, args.port), LabelServer)
    print(f"Labellisation : http://{args.host}:{args.port}")
    print(f"Dataset : {LabelServer.dataset}")
    server.serve_forever()


if __name__ == "__main__":
    main()
