from __future__ import annotations
"""
Admin commands for managing the doctors configuration.

/adicionar_medico  — interactive wizard to add or update a doctor
/listar_medicos    — list all configured doctors
/remover_medico    — remove a doctor by initials
"""

import json
import logging
import re
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

_DOCTORS_REPO = Path(__file__).parent.parent / "data" / "doctors.json"
_DOCTORS_TMP  = Path("/tmp/doctors.json")

# Conversation states
ASK_INITIALS      = 10
ASK_NAME          = 11
ASK_TRELLO_BOARD  = 12
ASK_DRIVE_FOLDER  = 13


def _load() -> dict:
    path = _DOCTORS_TMP if _DOCTORS_TMP.exists() else _DOCTORS_REPO
    with open(path) as f:
        return json.load(f)


def _save(data: dict) -> None:
    # Always write to /tmp (works on Vercel and locally)
    with open(_DOCTORS_TMP, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Also try repo file (works locally, falha silenciosamente na Vercel)
    try:
        with open(_DOCTORS_REPO, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _real_doctors(data: dict) -> dict:
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ── /listar_medicos ───────────────────────────────────────────────────────────

async def listar_medicos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doctors = _real_doctors(_load())
    if not doctors:
        await update.message.reply_text("Nenhum médico cadastrado ainda.")
        return

    lines = ["*Médicos cadastrados:*\n"]
    for key, doc in doctors.items():
        lines.append(f"• `{key}` — {doc['name']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /adicionar_medico wizard ──────────────────────────────────────────────────

async def adicionar_medico_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Vamos cadastrar um médico.\n\n"
        "Qual é a *sigla* usada no título do Google Doc? (ex: `GM`)",
        parse_mode="Markdown",
    )
    return ASK_INITIALS


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    initials = update.message.text.strip().upper()
    if not initials.isalpha():
        await update.message.reply_text("Sigla inválida. Use apenas letras (ex: `GM`).", parse_mode="Markdown")
        return ASK_INITIALS

    context.user_data["new_initials"] = initials
    await update.message.reply_text(f"Qual é o *nome completo* do médico?", parse_mode="Markdown")
    return ASK_NAME


async def ask_trello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Qual é o *ID do quadro no Trello*?\n\n"
        "Você encontra na URL do quadro: `trello.com/b/`*`ESTE_ID`*`/nome`",
        parse_mode="Markdown",
    )
    return ASK_TRELLO_BOARD


async def ask_drive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    # Accept full URL or just the ID
    trello_match = re.search(r'trello\.com/b/([a-zA-Z0-9_-]+)', raw)
    context.user_data["new_trello_board"] = trello_match.group(1) if trello_match else raw
    await update.message.reply_text(
        "Qual é o *link ou ID da pasta raiz* desse médico no Google Drive?\n\n"
        "Pode colar a URL completa da pasta.",
        parse_mode="Markdown",
    )
    return ASK_DRIVE_FOLDER


async def save_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw       = update.message.text.strip()
    # Accept full URL or just the ID
    drive_match = re.search(r'folders/([a-zA-Z0-9_-]+)', raw)
    drive_id  = drive_match.group(1) if drive_match else raw

    initials  = context.user_data["new_initials"]
    name      = context.user_data["new_name"]
    trello_id = context.user_data["new_trello_board"]

    data = _load()
    data[initials] = {
        "name":             name,
        "trello_board_id":  trello_id,
        "drive_folder_id":  drive_id,
    }
    _save(data)

    await update.message.reply_text(
        f"Médico *{name}* (`{initials}`) salvo com sucesso! ✅",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cadastro cancelado.")
    return ConversationHandler.END


# ── /remover_medico ───────────────────────────────────────────────────────────

async def remover_medico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Informe a sigla: `/remover_medico GM`", parse_mode="Markdown"
        )
        return

    initials = args[0].upper()
    data = _load()

    if initials not in data or initials.startswith("_"):
        await update.message.reply_text(f"Sigla `{initials}` não encontrada.", parse_mode="Markdown")
        return

    name = data[initials]["name"]
    del data[initials]
    _save(data)
    await update.message.reply_text(f"Médico *{name}* removido. ✅", parse_mode="Markdown")
