import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _build_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json), scopes=SCOPES
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json"),
            scopes=SCOPES,
        )
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    """Return existing folder ID or create it under parent."""
    # Escape single quotes in name for the query
    safe_name = name.replace("'", "\\'")
    query = (
        f"name='{safe_name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    result = service.files().list(q=query, fields="files(id, name)").execute()
    files  = result.get("files", [])

    if files:
        return files[0]["id"]

    metadata = {
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def ensure_day_folder(root_folder_id: str, year: int, month_name: str, day_folder: str) -> str:
    """
    Guarantee the path: root > year > month_name > day_folder
    Returns the public URL of the day folder.
    """
    service = _build_service()

    year_id  = _get_or_create_folder(service, str(year),    root_folder_id)
    month_id = _get_or_create_folder(service, month_name,   year_id)
    day_id   = _get_or_create_folder(service, day_folder,   month_id)

    return f"https://drive.google.com/drive/folders/{day_id}"


def ensure_story_folder(root_folder_id: str, folder_name: str) -> str:
    """
    Guarantee the path: root > STORIES > folder_name
    Returns the public URL of the story card folder.
    """
    service    = _build_service()
    stories_id = _get_or_create_folder(service, "STORIES",   root_folder_id)
    card_id    = _get_or_create_folder(service, folder_name, stories_id)
    return f"https://drive.google.com/drive/folders/{card_id}"
