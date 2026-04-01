import asyncio
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
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

logging.basicConfig(level=logging.INFO)


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
        "/cancelar          — cancelar operação",
        parse_mode="Markdown",
    )


async def _process_update(body: bytes) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não definido")

    persistence = PicklePersistence(filepath="/tmp/ptb_persistence")
    app = Application.builder().token(token).persistence(persistence).build()

    main_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & filters.Regex(r"docs\.google\.com"),
                receive_doc_link,
            )
        ],
        states={
            WAITING_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days)],
            WAITING_CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="main_conv",
        persistent=True,
    )

    add_doctor_conv = ConversationHandler(
        entry_points=[CommandHandler("adicionar_medico", adicionar_medico_start)],
        states={
            ASK_INITIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trello)],
            ASK_TRELLO_BOARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_drive)],
            ASK_DRIVE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_doctor)],
        },
        fallbacks=[CommandHandler("cancelar", cancel_admin)],
        name="add_doctor_conv",
        persistent=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar_medicos", listar_medicos))
    app.add_handler(CommandHandler("remover_medico", remover_medico))
    app.add_handler(add_doctor_conv)
    app.add_handler(main_conv)

    async with app:
        update = Update.de_json(json.loads(body), app.bot)
        await app.process_update(update)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        asyncio.run(_process_update(body))
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot online.")

    def log_message(self, *args):
        pass
