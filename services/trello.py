from __future__ import annotations
import os
import requests

BASE_URL = "https://api.trello.com/1"

MONTHS_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março",    4: "abril",
    5: "maio",    6: "junho",     7: "julho",     8: "agosto",
    9: "setembro",10: "outubro",  11: "novembro", 12: "dezembro",
}


def _auth() -> dict:
    return {
        "key":   os.getenv("TRELLO_API_KEY"),
        "token": os.getenv("TRELLO_TOKEN"),
    }


def _get(path: str, **params) -> list | dict:
    r = requests.get(f"{BASE_URL}{path}", params={**_auth(), **params})
    r.raise_for_status()
    return r.json()


def _post(path: str, **data) -> dict:
    r = requests.post(f"{BASE_URL}{path}", params=_auth(), json=data)
    r.raise_for_status()
    return r.json()


# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_list_id(board_id: str, month: int) -> str | None:
    """Find the list whose name contains the month name (case-insensitive)."""
    month_name = MONTHS_PT[month]
    lists = _get(f"/boards/{board_id}/lists")
    for lst in lists:
        if month_name.lower() in lst["name"].lower():
            return lst["id"]
    return None


def get_list_id_by_name(board_id: str, list_name: str) -> str | None:
    """Find a list by exact name (case-insensitive)."""
    lists = _get(f"/boards/{board_id}/lists")
    for lst in lists:
        if lst["name"].strip().lower() == list_name.strip().lower():
            return lst["id"]
    return None


def create_simple_card(board_id: str, list_name: str, title: str) -> dict:
    """Create a card without due date in a list found by name."""
    list_id = get_list_id_by_name(board_id, list_name)
    if not list_id:
        raise ValueError(
            f"Lista '{list_name}' não encontrada no quadro. "
            "Verifique o nome exato da lista no Trello."
        )
    return _post("/cards", name=title, idList=list_id)


def create_story_card(board_id: str, list_name: str, card_title: str, description: str) -> dict:
    """Create a story card in the given list."""
    list_id = get_list_id_by_name(board_id, list_name)
    if not list_id:
        lists = _get(f"/boards/{board_id}/lists")
        available = ", ".join(f"'{l['name']}'" for l in lists)
        raise ValueError(
            f"Lista '{list_name}' não encontrada.\n"
            f"Listas disponíveis: {available}"
        )
    return _post("/cards", name=card_title, desc=description, idList=list_id)


def get_label_id(board_id: str, label_name: str) -> str | None:
    """Find a label by name (case-insensitive)."""
    labels = _get(f"/boards/{board_id}/labels")
    for lbl in labels:
        if lbl.get("name", "").lower() == label_name.lower():
            return lbl["id"]
    return None


# ── Card creation ─────────────────────────────────────────────────────────────

def create_card(board_id: str, entry: dict, drive_url: str) -> dict:
    """
    Create a Trello card for a content entry.
    Returns the created card object.
    """
    list_id = get_list_id(board_id, entry["month"])
    if not list_id:
        raise ValueError(
            f"Lista '{MONTHS_PT[entry['month']]}' não encontrada no quadro. "
            "Verifique se a lista existe com esse nome."
        )

    # Build label list
    label_ids = []

    type_label = "Edição de Vídeo" if entry["format_type"] == "video" else "Designer"
    type_label_id = get_label_id(board_id, type_label)
    if type_label_id:
        label_ids.append(type_label_id)

    if entry["editor"]:
        editor_label_id = get_label_id(board_id, f"Edição por {entry['editor']}")
        if editor_label_id:
            label_ids.append(editor_label_id)

    # Build description
    description = entry["description"] + f"\n\n---\n📁 [Pasta no Drive]({drive_url})"

    due_date = f"{entry['year']}-{entry['month']:02d}-{entry['day_num']:02d}T12:00:00.000Z"

    card = _post(
        "/cards",
        name=entry["card_title"],
        desc=description,
        idList=list_id,
        idLabels=label_ids,
        due=due_date,
    )

    # Add comment mentioning the editor
    _post(
        f"/cards/{card['id']}/actions/comments",
        text="@isadorarodrigues117",
    )

    return card
