from __future__ import annotations
import re

# Matches lines like: "1. STORY – NAME" or "🎯 2. STORY – NAME"
CARD_PATTERN = re.compile(
    r'^[^\w\d]*(\d+)\.\s*STORY\s*[–\-]\s*(.+)',
    re.IGNORECASE,
)

# Strategy section marker — stop parsing cards after this
STRATEGY_MARKER = re.compile(r'^🔁')


def is_story_doc(lines: list[str]) -> bool:
    """Return True if the document contains story cards."""
    for line in lines:
        if CARD_PATTERN.match(line.strip()):
            return True
    return False


def extract_client_from_lines(lines: list[str], known_initials: list[str]) -> str | None:
    """
    Find client initials from the first few lines.
    Expects a line like 'FB - Roteiros de stories'.
    """
    for line in lines[:6]:
        stripped = line.strip().upper()
        for init in known_initials:
            init_up = init.upper()
            if (
                stripped.startswith(init_up + " ")
                or stripped.startswith(init_up + "-")
                or stripped.startswith(init_up + "–")
                or stripped == init_up
            ):
                return init
    return None


def _format_content(raw_lines: list[str]) -> str:
    """Clean up content: replace \\x0b (Google Docs soft break) with newlines."""
    joined = "\n".join(raw_lines)
    joined = joined.replace("\x0b", "\n")
    # Collapse 3+ newlines into 2
    joined = re.sub(r'\n{3,}', '\n\n', joined)
    return joined.strip()


def _build_card(num: int, name: str, lines: list[str]) -> dict:
    # Strip leading emoji/symbols from name for cleaner titles
    clean_name = re.sub(r'^[\s🎯🎭]+', '', name).strip()

    # Remove parenthetical descriptions for the folder name to keep it short
    folder_base = re.sub(r'\s*\(.*?\)\s*$', '', clean_name).strip()

    folder_name = f"{num:02d}. STORY – {folder_base}"
    card_title  = f"STORY – {clean_name}"

    return {
        "number":      num,
        "name":        clean_name,
        "folder_name": folder_name,
        "card_title":  card_title,
        "content":     _format_content(lines),
    }


def parse_story_cards(lines: list[str]) -> list[dict]:
    """
    Parse story cards from document lines.
    Returns list of dicts: {number, name, folder_name, card_title, content}.
    """
    cards: list[dict] = []
    current_num:  int | None  = None
    current_name: str | None  = None
    current_lines: list[str]  = []

    for line in lines:
        stripped = line.strip()

        # Stop at strategy section
        if STRATEGY_MARKER.match(stripped):
            break

        m = CARD_PATTERN.match(stripped)
        if m:
            if current_num is not None:
                cards.append(_build_card(current_num, current_name, current_lines))
            current_num   = int(m.group(1))
            current_name  = m.group(2).strip()
            current_lines = [stripped]
        elif current_num is not None:
            current_lines.append(line.rstrip())

    if current_num is not None:
        cards.append(_build_card(current_num, current_name, current_lines))

    return cards
