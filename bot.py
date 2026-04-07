import logging
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.main_flow import (
    receive_doc_link,
    receive_days,
    confirm,
    cancel,
    WAITING_DAYS,
    WAITING_CONFIRMATION,
)
from handlers.story_flow import (
    receive_story_list,
    confirm_stories,
    WAITING_STORY_LIST,
    WAITING_STORY_CONFIRMATION,
)
from handlers.admin import (
    adicionar_medico_start,
    ask_name,
    ask_trello,
    ask_drive,
    save_doctor,
    cancel_admin,
    listar_medicos,
    remover_medico,
    ASK_INITIALS,
    ASK_NAME,
    ASK_TRELLO_BOARD,
    ASK_DRIVE_FOLDER,
)
from handlers.bulk_list import (
    subir_lista_start,
    ask_list_name,
    ask_items,
    preview_items,
    bulk_confirm,
    cancel_bulk,
    ASK_DOCTOR,
    ASK_LIST_NAME,
    ASK_ITEMS,
    BULK_CONFIRMATION,
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, _) -> None:
    await update.message.reply_text(
        "Olá! Sou o bot de social media. 👋\n\n"
        "*Como usar:*\n"
        "1. Me manda o link do Google Doc\n"
        "2. Me diz quais dias subir (ex: `01 a 06`)\n"
        "3. Confirmo e crio tudo no Trello e Drive\n\n"
        "*Comandos:*\n"
        "/adicionar\\_medico — cadastrar médico\n"
        "/listar\\_medicos   — ver médicos cadastrados\n"
        "/remover\\_medico   — remover médico\n"
        "/subir\\_lista      — subir lista sem data para o Trello\n"
        "/cancelar          — cancelar operação",
        parse_mode="Markdown",
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não definido no .env")

    app = Application.builder().token(token).build()

    # ── Main content flow ─────────────────────────────────────────────────────
    main_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & filters.Regex(r"docs\.google\.com"),
                receive_doc_link,
            )
        ],
        states={
            WAITING_DAYS:                [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days)],
            WAITING_CONFIRMATION:        [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            WAITING_STORY_LIST:          [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_story_list)],
            WAITING_STORY_CONFIRMATION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_stories)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
    )

    # ── Admin: add doctor ─────────────────────────────────────────────────────
    add_doctor_conv = ConversationHandler(
        entry_points=[CommandHandler("adicionar_medico", adicionar_medico_start)],
        states={
            ASK_INITIALS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trello)],
            ASK_TRELLO_BOARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_drive)],
            ASK_DRIVE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_doctor)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_admin)],
    )

    # ── Bulk list flow ────────────────────────────────────────────────────────
    bulk_list_conv = ConversationHandler(
        entry_points=[CommandHandler("subir_lista", subir_lista_start)],
        states={
            ASK_DOCTOR:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_list_name)],
            ASK_LIST_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_items)],
            ASK_ITEMS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, preview_items)],
            BULK_CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_confirm)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_bulk)],
    )

    app.add_handler(CommandHandler("start",          start))
    app.add_handler(CommandHandler("listar_medicos", listar_medicos))
    app.add_handler(CommandHandler("remover_medico", remover_medico))
    app.add_handler(add_doctor_conv)
    app.add_handler(bulk_list_conv)
    app.add_handler(main_conv)

    logger.info("Bot iniciado.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
