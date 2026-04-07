from __future__ import annotations
"""
/subir_lista flow:
  1. User sends /subir_lista
  2. Bot shows list of doctors — user picks by number
  3. Bot asks for the Trello list name
  4. Bot asks for the numbered content list
  5. Bot shows preview and asks confirmation
  6. On confirmation, cards are created
"""

import json
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from services.trello import create_simple_card

logger = logging.getLogger(__name__)

ASK_DOCTOR       = 10
ASK_LIST_NAME    = 11
ASK_ITEMS        = 12
BULK_CONFIRMATION = 13

_DOCTORS_FILE = Path(__file__).parent.parent / "data" / "doctors.json"


def _load_doctors() -> dict:
    tmp = Path("/tmp/doctors.json")
    path = tmp if tmp.exists() else _DOCTORS_FILE
    with open(path) as f:
        return json.load(f)


def _parse_items(text: str) -> list[str]:
    """Extract item titles from a numbered list, ignoring empty lines."""
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove leading number + dot/parenthesis  (e.g. "1." "1)" "1 -")
        cleaned = re.sub(r"^\d+[\.\)\-]\s*", "", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


# ── Entry point ───────────────────────────────────────────────────────────────

async def subir_lista_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doctors = _load_doctors()
    real_doctors = {k: v for k, v in doctors.items() if not k.startswith("_")}

    if not real_doctors:
        await update.message.reply_text(
            "Nenhum médico configurado. Use /adicionar\\_medico para cadastrar.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data["doctor_map"] = real_doctors

    lines = ["Qual cliente? Responda com o número:\n"]
    for i, (initials, doc) in enumerate(real_doctors.items(), start=1):
        lines.append(f"{i}. {doc['name']} ({initials})")
    await update.message.reply_text("\n".join(lines))
    return ASK_DOCTOR


# ── Step 2: pick doctor ───────────────────────────────────────────────────────

async def ask_list_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    doctor_map: dict = context.user_data["doctor_map"]
    doctors_list = list(doctor_map.items())

    if not text.isdigit() or not (1 <= int(text) <= len(doctors_list)):
        await update.message.reply_text(
            f"Manda um número entre 1 e {len(doctors_list)}."
        )
        return ASK_DOCTOR

    initials, doctor = doctors_list[int(text) - 1]
    context.user_data["initials"] = initials
    context.user_data["doctor"]   = doctor

    await update.message.reply_text(
        f"Cliente: *{doctor['name']}* ✅\n\n"
        "Qual o nome da lista no Trello? (ex: `Backlog`)",
        parse_mode="Markdown",
    )
    return ASK_LIST_NAME


# ── Step 3: list name → ask items ─────────────────────────────────────────────

async def ask_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    list_name = update.message.text.strip()
    if not list_name:
        await update.message.reply_text("Nome da lista não pode ser vazio. Tenta de novo.")
        return ASK_LIST_NAME

    context.user_data["list_name"] = list_name
    await update.message.reply_text(
        f"Lista: *{list_name}* ✅\n\n"
        "Agora manda os itens (um por linha, pode ser numerado):\n\n"
        "_Ex:_\n`1. STORY\n2. Reels\n3. Post feed`",
        parse_mode="Markdown",
    )
    return ASK_ITEMS


# ── Step 4: receive items → preview ──────────────────────────────────────────

async def preview_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    items = _parse_items(update.message.text)

    if not items:
        await update.message.reply_text(
            "Não encontrei nenhum item. Manda a lista de novo."
        )
        return ASK_ITEMS

    context.user_data["items"] = items

    doctor    = context.user_data["doctor"]
    list_name = context.user_data["list_name"]

    preview_lines = [
        f"*{len(items)} card(s) para {doctor['name']}*",
        f"Lista: _{list_name}_\n",
    ]
    for item in items:
        preview_lines.append(f"• {item}")
    preview_lines.append("\nConfirmar? Responda *sim* ou *não*")

    await update.message.reply_text("\n".join(preview_lines), parse_mode="Markdown")
    return BULK_CONFIRMATION


# ── Step 5: confirmation ──────────────────────────────────────────────────────

async def bulk_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip().lower() not in ("sim", "s", "yes", "y"):
        await update.message.reply_text("Cancelado. ❌")
        return ConversationHandler.END

    doctor    = context.user_data["doctor"]
    list_name = context.user_data["list_name"]
    items     = context.user_data["items"]

    await update.message.reply_text("Criando cards... ⏳")

    results = []
    errors  = []

    for title in items:
        try:
            card = create_simple_card(doctor["trello_board_id"], list_name, title)
            results.append(f"✅ {card['name']}")
        except Exception as e:
            logger.error("Erro ao criar card '%s': %s", title, e)
            errors.append(f"❌ {title}: {e}")

    summary = "\n".join(results + errors)
    await update.message.reply_text(f"Pronto! 🎉\n\n{summary}")
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operação cancelada. ❌")
    return ConversationHandler.END
