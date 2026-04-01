import os
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _build_service():
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
