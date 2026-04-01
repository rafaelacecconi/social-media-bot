from __future__ import annotations
import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from utils.parser import detect_month_year, extract_initials_from_title, parse_entries

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


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
    return build("docs", "v1", credentials=creds)


def get_doc_title(doc_id: str) -> str:
    service = _build_service()
    doc = service.documents().get(documentId=doc_id).execute()
    return doc.get("title", "")


def extract_text_lines(document: dict) -> list[str]:
    """
    Walk the Google Doc body and return a flat list of text lines.
    Hyperlinks are preserved as Markdown: [texto](url)
    """
    lines = []
    body = document.get("body", {})

    for element in body.get("content", []):
        if "paragraph" not in element:
            continue

        parts = []
        for run in element["paragraph"].get("elements", []):
            text_run = run.get("textRun", {})
            text     = text_run.get("content", "")
            link_obj = text_run.get("textStyle", {}).get("link", {})
            url      = link_obj.get("url", "") if link_obj else ""

            if url and text.strip():
                parts.append(f"[{text.strip()}]({url})")
            else:
                parts.append(text)

        lines.append("".join(parts))

    return lines


def get_entries_from_doc(doc_id: str, days: list[int], known_initials: list[str]) -> tuple[list[dict], str, str]:
    """
    Fetch the document, detect doctor + month/year, parse requested days.
    Returns (entries, initials, doctor_name_hint).
    """
    service = _build_service()
    document = service.documents().get(documentId=doc_id).execute()
    title    = document.get("title", "")

    month, year = detect_month_year(title)
    initials    = extract_initials_from_title(title, known_initials)

    lines   = extract_text_lines(document)
    entries = parse_entries(lines, days, month, year, initials or "??")

    return entries, initials, title
