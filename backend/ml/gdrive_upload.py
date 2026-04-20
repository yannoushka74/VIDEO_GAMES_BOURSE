#!/usr/bin/env python3
"""Upload/mise à jour de fichiers Markdown dans le vault Obsidian (Google Drive).

Utilise OAuth2 avec le compte Google personnel (pas le service account).

Première utilisation :
    1. Aller sur https://console.cloud.google.com/apis/credentials
    2. Créer un "OAuth 2.0 Client ID" de type "Desktop app"
    3. Télécharger le JSON → sauver comme /root/RAG_DATA_ENGINEER/oauth_credentials.json
    4. Lancer ce script : python ml/gdrive_upload.py
    5. Suivre le lien dans le terminal pour autoriser l'accès
    6. Le token sera sauvé dans /root/RAG_DATA_ENGINEER/gdrive_token.json

Utilisation suivante : le token est réutilisé automatiquement.
"""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDS_PATH = '/root/RAG_DATA_ENGINEER/oauth_credentials.json'
TOKEN_PATH = '/root/RAG_DATA_ENGINEER/gdrive_token.json'

# Vault Obsidian → 02-projects/personal/
PERSONAL_FOLDER_ID = '100ZIq33Tsf4V2ccz7N7XJh7yRIHi_qur'


def get_credentials():
    """Obtient les credentials OAuth2 (avec refresh automatique)."""
    creds = None
    token_path = Path(TOKEN_PATH)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_console()
        token_path.write_text(creds.to_json())

    return creds


def get_service():
    return build('drive', 'v3', credentials=get_credentials())


def create_folder(service, name, parent_id):
    """Crée un dossier ou retourne l'existant."""
    results = service.files().list(
        q=f'"{parent_id}" in parents and name="{name}" and mimeType="application/vnd.google-apps.folder" and trashed=false',
        fields='files(id)'
    ).execute()
    if results['files']:
        return results['files'][0]['id']
    meta = {'name': name, 'parents': [parent_id], 'mimeType': 'application/vnd.google-apps.folder'}
    f = service.files().create(body=meta, fields='id').execute()
    return f['id']


def upload_md(service, name, content, parent_id):
    """Upload un fichier .md (crée ou met à jour)."""
    results = service.files().list(
        q=f'"{parent_id}" in parents and name="{name}" and trashed=false',
        fields='files(id)'
    ).execute()
    media = MediaInMemoryUpload(content.encode('utf-8'), mimetype='text/markdown')
    if results['files']:
        service.files().update(fileId=results['files'][0]['id'], media_body=media).execute()
        print(f'  Updated: {name}')
        return results['files'][0]['id']
    meta = {'name': name, 'parents': [parent_id]}
    f = service.files().create(body=meta, media_body=media, fields='id').execute()
    print(f'  Created: {name}')
    return f['id']


def upload_folder(service, local_dir: str, parent_id: str):
    """Upload tous les .md d'un dossier local vers un dossier Drive."""
    local_path = Path(local_dir)
    folder_name = local_path.name
    folder_id = create_folder(service, folder_name, parent_id)
    print(f'Folder: {folder_name} ({folder_id})')

    for md_file in sorted(local_path.glob('*.md')):
        content = md_file.read_text(encoding='utf-8')
        upload_md(service, md_file.name, content, folder_id)

    return folder_id


if __name__ == '__main__':
    import sys
    service = get_service()

    local_dir = sys.argv[1] if len(sys.argv) > 1 else '/root/obsidian-export/video-games-bourse'
    parent_id = sys.argv[2] if len(sys.argv) > 2 else PERSONAL_FOLDER_ID

    upload_folder(service, local_dir, parent_id)
    print('\nDone!')
