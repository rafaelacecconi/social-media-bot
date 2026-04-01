from __future__ import annotations
import re
from datetime import datetime

DAYS_PT = {
    "SEGUNDA": "segunda-feira",
    "TERÇA":   "terça-feira",
    "TERCA":   "terça-feira",
    "QUARTA":  "quarta-feira",
    "QUINTA":  "quinta-feira",
    "SEXTA":   "sexta-feira",
    "SÁBADO":  "sábado",
    "SABADO":  "sábado",
    "DOMINGO": "domingo",
}

MONTHS_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março",    4: "abril",
    5: "maio",    6: "junho",     7: "julho",     8: "agosto",
    9: "setembro",10: "outubro",  11: "novembro", 12: "dezembro",
}

MONTHS_REVERSE = {v.upper(): k for k, v in MONTHS_PT.items()}
MONTHS_REVERSE["MARCO"] = 3

VIDEO_FORMATS    = {"REELS", "REEL", "VIDEO", "VÍDEO", "REELS/VIDEO"}
DESIGNER_FORMATS = {"FEED", "CARROSSEL", "CARROSEL", "STORIES", "STORY", "DESTAQUE"}

# Matches lines like: "02 - SEGUNDA - REELS - Tema do conteúdo"
ENTRY_PATTERN = re.compile(
    r'^(\d{1,2})\s*[-–]\s*'
    r'(SEGUNDA|TERÇA|TERCA|QUARTA|QUINTA|SEXTA|SÁBADO|SABADO|DOMINGO)\s*[-–]\s*'
    r'(.+)',
    re.IGNORECASE,
)


def parse_day_range(text: str) -> list[int]:
    """Parse '01 a 06' or '01, 03, 05' or '1 2 3' into list of ints."""
    text = text.strip()
    range_match = re.match(r'(\d{1,2})\s+a\s+(\d{1,2})', text, re.IGNORECASE)
    if range_match:
        start, end = int(range_match.group(1)), int(range_match.group(2))
        return list(range(start, end + 1))
    nums = re.findall(r'\d{1,2}', text)
    return [int(n) for n in nums] if nums else []


def detect_month_year(title: str) -> tuple[int, int]:
    """Try to extract month and year from doc title; fallback to current date."""
    title_upper = title.upper()
    for name, num in MONTHS_REVERSE.items():
        if name in title_upper:
            year_match = re.search(r'\b(20\d{2})\b', title)
            year = int(year_match.group(1)) if year_match else datetime.now().year
            return num, year
    now = datetime.now()
    return now.month, now.year


def extract_initials_from_title(title: str, known_initials: list[str]) -> str | None:
    """Find which known initials appear in the doc title."""
    title_upper = title.upper()
    for initials in known_initials:
        if initials.upper() in title_upper:
            return initials
    return None


def split_into_blocks(lines: list[str]) -> list[list[str]]:
    """Split document lines into per-entry blocks."""
    blocks, current = [], []
    for line in lines:
        if ENTRY_PATTERN.match(line.strip()):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_block(lines: list[str], month: int, year: int, doctor_initials: str) -> dict | None:
    """Parse a single content block into a structured entry dict."""
    if not lines:
        return None

    first_line = lines[0].strip()
    match = ENTRY_PATTERN.match(first_line)
    if not match:
        return None

    day_num      = int(match.group(1))
    day_raw      = match.group(2).upper()
    rest         = match.group(3).strip()

    # rest = "REELS - Tema do conteúdo"
    parts        = rest.split("-", 1)
    format_raw   = parts[0].strip().upper()
    theme        = parts[1].strip() if len(parts) > 1 else rest

    # Editor name
    editor = ""
    for line in lines[1:]:
        editor_match = re.match(r'Edição\s*:\s*(\w+)', line.strip(), re.IGNORECASE)
        if editor_match:
            editor = editor_match.group(1).capitalize()
            break

    day_name   = DAYS_PT.get(day_raw, day_raw.lower())
    month_name = MONTHS_PT[month]

    format_type = "video" if format_raw in VIDEO_FORMATS else "designer"

    # Full description block — join with double newline so Trello Markdown
    # renders each line as a separate paragraph with visible spacing.
    result = []
    for line in lines:
        stripped = line.rstrip()
        result.append(stripped)
    # Collapse 3+ consecutive blank lines into 2, then join with \n\n
    import re as _re
    raw = "\n".join(result)
    raw = _re.sub(r'\n{3,}', '\n\n', raw)
    # Convert single newlines between content to double newlines
    full_desc = _re.sub(r'(?<!\n)\n(?!\n)', '\n\n', raw).strip()

    return {
        "day_num":         day_num,
        "day_name":        day_name,
        "format_raw":      format_raw,
        "format_type":     format_type,
        "theme":           theme,
        "editor":          editor,
        "card_title":      f"[{doctor_initials}] {day_num:02d}-{month:02d} - {day_name}",
        "day_folder":      f"{day_num:02d}{month:02d}",
        "month":           month,
        "month_name":      month_name,
        "year":            year,
        "description":     full_desc,
    }


def parse_entries(lines: list[str], days: list[int], month: int, year: int, initials: str) -> list[dict]:
    """Extract and parse only the requested days from document lines."""
    blocks  = split_into_blocks(lines)
    entries = []
    for block in blocks:
        entry = parse_block(block, month, year, initials)
        if entry and entry["day_num"] in days:
            entries.append(entry)
    return entries
