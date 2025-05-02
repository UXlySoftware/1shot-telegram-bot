#!/usr/bin/env python
import os
import logging
from http import HTTPStatus
from contextlib import asynccontextmanager

from objects import (
    TransactionMemo,
    TxType,
    ConversationState
)

from chattracker import track_chats

from deploytoken import get_token_deployment_conversation_handler

from uxly_1shot_client import (
    WebhookPayload,
)

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ChatMemberHandler,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    TypeHandler,
)
from telegram.constants import ParseMode

import uvicorn



# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Define configuration constants
URL = "rapid-clam-infinitely.ngrok-free.app"
PORT = 8000
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # nosec B105

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot and show the main menu."""

    buttons = []

    text = "Welcome to Coinucopia.Finance, lets get started! 🥳\n\n"
    text += "Looks like you are new, you'll need to set an EVM address to receive tokens from Coinucopia.Finance.\n\n"
    text += "You can set an address by clicking the \"📍 Set My Address\" button and pasting in a valid EVM address.\n\n"
    text += "Be sure this address is accessible across networks."
    buttons.append([InlineKeyboardButton("🚀 Deploy a Token", callback_data="deploytoken")])

    keyboard = InlineKeyboardMarkup(buttons)

    # If we're starting over we don't need to send a new message
    if context.user_data.get(ConversationState.START_OVER):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    context.user_data[ConversationState.START_OVER] = False
    return ConversationState.START_ROUTES

async def webhook_update(update: WebhookPayload, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming webhook updates."""
    # Extract the payload from the update
    event_type = update.eventName

    if event_type == "TransactionExecutionSuccess":
        # check for the Transaction Memo, if its not set, we don't know what to do with it
        if not update.data.transaction_execution_memo:
            logger.error(f"TransactionMemo is null: {update.data.transaction_execution_id}")
            return
        
        tx_memo = TransactionMemo.model_validate_json(update.data.transaction_execution_memo)
        if tx_memo.tx_type == TxType.TOKEN_CREATION:
            token_address = None
            for log in update.data.logs:
                if log.name == "TokenCreated":
                    token_address = log.args[0]
        elif tx_memo.tx_type == TxType.TOKENS_TRANSFERRED:
            if tx_memo.note_to_user:
                await context.bot.send_message(
                    chat_id=tx_memo.associated_user_id,
                    text=tx_memo.note_to_user,
                    parse_mode=ParseMode.HTML
                )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize and shutdown the Telegram bot."""
    app.application = (
        Application.builder().token(TOKEN).updater(None).build()
    )

    coinucopia_entrypoint_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ConversationState.START_ROUTES: [
                CommandHandler("start", start),
                get_token_deployment_conversation_handler(),
                CallbackQueryHandler(start, pattern="^start$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", canceler)
        ],
        per_chat=True,
    )

    # handle when the user calls /start
    app.application.add_handler(coinucopia_entrypoint_handler)

    # handles updates from 1shot by selecting Telegram updates of type WebhookPayload
    app.application.add_handler(TypeHandler(type=WebhookPayload, callback=webhook_update))

    # track what chats the bot is in, can be useful for group-based features
    app.application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    # TODO: use secret-token: https://docs.python-telegram-bot.org/en/stable/telegram.bot.html#telegram.Bot.set_webhook.params.secret_token
    await app.application.bot.set_webhook(url=f"{URL}/telegram", allowed_updates=Update.ALL_TYPES)
    await app.application.initialize()
    await app.application.start()

    yield
    await app.application.stop()

# FastAPI app
app = FastAPI(lifespan=lifespan)

@app.post("/telegram")
async def telegram(request: Request):
    data = await request.json()
    update = Update.de_json(data, app.application.bot)
    await app.application.update_queue.put(update)
    return Response(status_code=HTTPStatus.OK)

# This route is for 1shot to send updates to the bot about transactions that the bot initiated
@app.api_route("/1shot", methods=["POST"])
async def oneshot_updates(request: Request):
    try:
        body = await request.json()
        webhook_payload = WebhookPayload(**body)
        # we put objects of type WebhookPayload into the update queue which will trigger the webhook_update handler via the TypeHandler registered on startup
        await app.application.update_queue.put(webhook_payload)
        return Response(status_code=HTTPStatus.OK)
    except Exception:
        return Response(status_code=HTTPStatus.NOT_ACCEPTABLE)

@app.get("/healthcheck")
async def health():
    return PlainTextResponse("The bot is still running fine :)", status_code=HTTPStatus.OK)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
