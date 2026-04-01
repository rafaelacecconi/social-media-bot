from __future__ import annotations
"""
Main conversation flow:
  1. User sends Google Doc link
  2. Bot identifies the doctor and asks which days to process
  3. User replies with day range  (ex: "01 a 06" or "01, 03, 05")
  4. Bot shows a preview and asks for confirmation
  5. On confirmation, folders and cards are created
"""

import re
import json
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from services.docs  import get_entries_from_doc
from services.drive import ensure_day_folder
from services.trello import create_card
from utils.parser  import parse_day_range

logger = logging.getLogger(__name__)

# Conversation states
WAITING_DAYS         = 1
WAITING_CONFIRMATION = 2

DOC_ID_RE = re.compile(r'/document/d/([a-zA-Z0-9_-]+)')


def _load_doctors() -> dict:
    with open("data/doctors.json") as f:
        return json.load(f)


def _extract_doc_id(url: str) -> str | None:
    m = DOC_ID_RE.search(url)
    return m.group(1) if m else None


def _build_preview(entries: list[dict], doctor: dict) -> str:
    type_icon = {"video": "🎬", "designer": "🎨"}
    lines = [f"*{len(entries)} card(s) para {doctor['name']}:*\n"]
    for e in entries:
        icon = type_icon.get(e["format_type"], "📄")
        lines.append(
            f"• *{e['card_title']}*\n"
            f"  {icon} {'Edição de Vídeo' if e['format_type'] == 'video' else 'Designer'}"
            + (f" | {e['editor']}" if e["editor"] else "") + "\n"
        )
    lines.append("Confirmar? Responda *sim* ou *não*")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

async def receive_doc_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url    = update.message.text.strip()
    doc_id = _extract_doc_id(url)

    if not doc_id:
        await update.message.reply_text(
            "Não consegui identificar o link do Google Doc. "
            "Manda o link completo do documento."
        )
        return ConversationHandler.END

    doctors = _load_doctors()
    # Remove the example entry
    real_doctors = {k: v for k, v in doctors.items() if not k.startswith("_")}

    if not real_doctors:
        await update.message.reply_text(
            "Nenhum médico configurado ainda. Use /adicionar\\_medico para cadastrar.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text("Lendo o documento... ⏳")

    try:
        entries_placeholder, initials, title = get_entries_from_doc(
            doc_id, list(range(1, 32)), list(real_doctors.keys())
        )
    except Exception as e:
        logger.error("Erro ao ler o doc: %s", e)
        await update.message.reply_text(
            f"Erro ao acessar o documento: `{e}`\n\n"
            "Verifique se o documento está compartilhado com a conta de serviço.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    if not initials or initials not in real_doctors:
        await update.message.reply_text(
            f"Não reconheci o médico pelo título: *{title}*\n\n"
            "Use /listar\\_medicos para ver as siglas cadastradas.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data["doc_id"]   = doc_id
    context.user_data["initials"] = initials
    context.user_data["doctor"]   = real_doctors[initials]

    await update.message.reply_text(
        f"Documento de *{real_doctors[initials]['name']}* detectado ✅\n\n"
        "Quais dias processar?\n"
        "Ex: `01 a 06` ou `01, 03, 05`",
        parse_mode="Markdown",
    )
    return WAITING_DAYS


# ── Step 2: receive days ──────────────────────────────────────────────────────

async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    days = parse_day_range(update.message.text.strip())

    if not days:
        await update.message.reply_text(
            "Não entendi. Tenta assim:\n`01 a 06` ou `01, 03, 05`",
            parse_mode="Markdown",
        )
        return WAITING_DAYS

    await update.message.reply_text("Buscando os dias no documento... ⏳")

    doc_id   = context.user_data["doc_id"]
    initials = context.user_data["initials"]
    doctor   = context.user_data["doctor"]

    try:
        entries, _, _ = get_entries_from_doc(doc_id, days, [initials])
    except Exception as e:
        logger.error("Erro ao ler o doc: %s", e)
        await update.message.reply_text(f"Erro ao ler o documento: `{e}`", parse_mode="Markdown")
        return ConversationHandler.END

    if not entries:
        await update.message.reply_text(
            f"Não encontrei conteúdo para os dias: {', '.join(str(d) for d in days)}\n"
            "Verifique se esses dias estão no documento."
        )
        return WAITING_DAYS

    context.user_data["entries"] = entries
    preview = _build_preview(entries, doctor)
    await update.message.reply_text(preview, parse_mode="Markdown")
    return WAITING_CONFIRMATION


# ── Step 3: confirmation ──────────────────────────────────────────────────────

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text.strip().lower()

    if response not in ("sim", "s", "yes", "y"):
        await update.message.reply_text("Cancelado. ❌")
        return ConversationHandler.END

    entries  = context.user_data["entries"]
    doctor   = context.user_data["doctor"]
    initials = context.user_data["initials"]

    await update.message.reply_text("Criando pastas e cards... ⏳")

    results = []
    errors  = []

    for entry in entries:
        try:
            # 1. Create / find Drive folder
            drive_url = ensure_day_folder(
                root_folder_id=doctor["drive_folder_id"],
                year=entry["year"],
                month_name=entry["month_name"],
                day_folder=entry["day_folder"],
            )

            # 2. Create Trello card
            card = create_card(
                board_id=doctor["trello_board_id"],
                entry=entry,
                drive_url=drive_url,
            )

            results.append(f"✅ {card['name']}")
        except Exception as e:
            logger.error("Erro em %s: %s", entry.get("card_title"), e)
            errors.append(f"❌ {entry.get('card_title', '?')}: {e}")

    summary = "\n".join(results + errors)
    await update.message.reply_text(
        f"Pronto! 🎉\n\n{summary}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operação cancelada. ❌")
    return ConversationHandler.END
