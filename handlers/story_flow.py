from __future__ import annotations
"""
Story flow:
  1. Doc link received → detected as story doc (called from main_flow router)
  2. Bot shows found cards and asks which Trello list to use
  3. User replies with list name
  4. Bot shows preview and asks for confirmation
  5. On confirmation, creates Drive folders + Trello cards
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from services.drive  import ensure_story_folder
from services.trello import create_story_card
from utils.story_parser import parse_story_cards

logger = logging.getLogger(__name__)

# States (continuing from main_flow's 1-2)
WAITING_STORY_LIST         = 3
WAITING_STORY_CONFIRMATION = 4


def _build_preview(cards: list[dict], client_name: str) -> str:
    lines = [f"*{len(cards)} card(s) para {client_name}:*\n"]
    for c in cards:
        lines.append(f"• *{c['card_title']}*")
    lines.append(f"\nQual lista do Trello usar?\n(ex: `Roteiros`, `Stories`, `Abril`)")
    return "\n".join(lines)


async def start_story_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Called from main_flow.receive_doc_link when a story doc is detected.
    context.user_data must already have: doc_id, initials, doctor, story_cards.
    """
    cards       = context.user_data["story_cards"]
    doctor      = context.user_data["doctor"]
    preview     = _build_preview(cards, doctor["name"])

    await update.message.reply_text(preview, parse_mode="Markdown")
    return WAITING_STORY_LIST


async def receive_story_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    list_name = update.message.text.strip()
    cards     = context.user_data["story_cards"]
    doctor    = context.user_data["doctor"]

    context.user_data["story_list"] = list_name

    lines = [f"*Resumo — lista: `{list_name}`*\n"]
    for c in cards:
        lines.append(f"• {c['card_title']}")
        lines.append(f"  📁 Pasta: `{c['folder_name']}`\n")
    lines.append("Confirmar? Responda *sim* ou *não*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    return WAITING_STORY_CONFIRMATION


async def confirm_stories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text.strip().lower()

    if response not in ("sim", "s", "yes", "y"):
        await update.message.reply_text("Cancelado. ❌")
        return ConversationHandler.END

    cards     = context.user_data["story_cards"]
    doctor    = context.user_data["doctor"]
    list_name = context.user_data["story_list"]

    await update.message.reply_text("Criando pastas e cards... ⏳")

    results = []
    errors  = []

    for card in cards:
        try:
            # 1. Drive folder: root > STORIES > folder_name
            drive_url = ensure_story_folder(
                root_folder_id=doctor["drive_folder_id"],
                folder_name=card["folder_name"],
            )

            # 2. Trello card
            description = card["content"] + f"\n\n---\n📁 [Pasta no Drive]({drive_url})"
            create_story_card(
                board_id=doctor["trello_board_id"],
                list_name=list_name,
                card_title=card["card_title"],
                description=description,
            )

            results.append(f"✅ {card['card_title']}")
        except Exception as e:
            logger.error("Erro em %s: %s", card.get("card_title"), e)
            errors.append(f"❌ {card.get('card_title', '?')}: {e}")

    summary = "\n".join(results + errors)
    await update.message.reply_text(f"Pronto! 🎉\n\n{summary}")
    return ConversationHandler.END
