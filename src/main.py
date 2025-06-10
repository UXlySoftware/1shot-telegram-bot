#!/usr/bin/env python
import os
import logging
from http import HTTPStatus
from contextlib import asynccontextmanager

# useful object patterns for a Telegram bot that interacts with the 1Shot API
from objects import (
    TransactionMemo,
    TxType,
    ConversationState
)

# the file contains various helper functions for the bot
from helpers import (
    canceler,
    get_token_deployer_endpoint_creation_payload, 
    webhookAuthenticator
)

# this file shows how you can track what chats your bot has been added to
from chattracker import track_chats

# this file shows how you can implement a non-trivial conversation flow that deploys and ERC20 token
from deploytoken import (
    get_token_deployment_conversation_handler,
    successful_token_deployment
)

# Auth against 1Shot API is done in oneshot.py where we implement a singleton pattern
from oneshot import (
    oneshot_client, # the 1Shot API async client that we instantiated in oneshot.py
    BUSINESS_ID # The organization id for your 1Shot API account
)

# the 1Shot Python SDK implements a helpful Pydantic dataclass model for Webhook callback payloads
from uxly_1shot_client import WebhookPayload

from fastapi import FastAPI, Request, HTTPException, Depends
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

URL = os.getenv("TUNNEL_BASE_URL") # this is the base url where Telegram will send update callbacks to
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Get this token from @BotFather
PORT = 8000 # The port that uvicorn will attach to

# This is an entrypoint handler for the example bot, it gets triggered when a user types /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot and show the main menu."""

    buttons = []

    text = "1Shot API is the easiest way to build Telegram bots with onchain functionality!\n\n"
    text += "Use this simple bot as a starting point\n\n"
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

# This handles webhooks coming from 1Shot API
async def webhook_update(update: WebhookPayload, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming webhook updates."""
    # Extract the payload from the update
    event_type = update.event_name

    if event_type == "TransactionExecutionSuccess":
        # check for the Transaction Memo, if its not set, we don't know what to do with it
        if not update.data.transaction_execution_memo:
            logger.error(f"TransactionMemo is null: {update.data.transaction_execution_id}")
            return
        
        tx_memo = TransactionMemo.model_validate_json(update.data.transaction_execution_memo)

        # Check what kind of transaction was executed based on the memo and handle appropriately for you application
        if tx_memo.tx_type == TxType.TOKEN_CREATION:
            token_address = None
            for log in update.data.logs:
                if log.name == "TokenCreated":
                    token_address = log.args[0]
            await successful_token_deployment(token_address, tx_memo, context)
        else:
            # implement other transaction types as needed
            logger.error(f"Unknown transaction type: {tx_memo.tx_type}")

# lifespane is used by FastAPI on startup and shutdown: https://fastapi.tiangolo.com/advanced/events/
# When the server is shutting down, the code after "yield" will be executed when shutting down
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to initialize and shutdown the Telegram bot."""
    app.application = (
        Application.builder().token(TOKEN).updater(None).build()
    )

    # lets start by checking that we have a wallet provisioned for our 1Shot API account on the Sepolia network
    # if not we will exit since we must have one to continue
    wallets = await oneshot_client.wallets.list(BUSINESS_ID, {"chain_id": "11155111"})
    if not ((len(wallets.response) >= 1) and (float(wallets.response[0].account_balance_details.balance) > 0.0001)):
        raise RuntimeError(
            "Escrow wallet not provisioned or insufficient balance on the Sepolia network. "
            "Please ensure an escrow wallet exists and has sufficient funds by logging into https://app.1shotapi.dev/escrow-wallets."
        )
    else:
        logger.info("Escrow wallet is provisioned and has sufficient funds.")

    # to keep this demo self contained, we are going to check our 1Shot API account for an existing contract method endpoint for the 
    # contract at 0xA1BfEd6c6F1C3A516590edDAc7A8e359C2189A61 on the Sepolia network, if we don't have one, we'll create it automatically
    # then we'll use that endpoint in the conversation flow to deploy tokens from a Telegram conversation
    # for a more serious application you will probably create your required contract method endpoints ahead of time
    # and input their contract method ids as environment variables
    contract_methods = await oneshot_client.contract_methods.list(
        business_id=BUSINESS_ID,
        params={"chain_id": "11155111", "name": "1Shot Demo Sepolia Token Deployer"}
    )
    if len(contract_methods.response) == 0:
        logger.info("Creating new smart contract method for token deployer contract.")
        deployer_endpoint_payload = get_token_deployer_endpoint_creation_payload(
            chain_id="11155111",
            contract_address="0xA1BfEd6c6F1C3A516590edDAc7A8e359C2189A61",
            escrow_wallet_id=wallets.response[0].id,
            callback=f"{URL}/1shot"
        )
        contract_method = await oneshot_client.contract_method.create(
            business_id=BUSINESS_ID,
            params=deployer_endpoint_payload
        )
    else:
        logger.info(f"Transaction endpoint already exists, skipping creation.")
        
    # Here is where we register the functionality of our Telegram bot, starting with a ConversationHandler
    # You can nest conversation flows inside each other for more complex applications: https://docs.python-telegram-bot.org/en/stable/examples.nestedconversationbot.html
    entrypoint_handler = ConversationHandler(
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
    app.application.add_handler(entrypoint_handler)

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

# This route is for Telegram to send Updates to the bot about message and interactions from users
# Its more efficient that using long polling
@app.post("/telegram")
async def telegram(request: Request):
    data = await request.json()
    update = Update.de_json(data, app.application.bot)
    await app.application.update_queue.put(update)
    return Response(status_code=HTTPStatus.OK)

# This route is for 1shot to send updates to the bot about transactions that the bot initiated
# check out the webhookAuthenticator class in helpers.py for how to verify the signature
# https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/
@app.api_route("/1shot", methods=["POST"], dependencies=[Depends(webhookAuthenticator())])
async def oneshot_updates(request: Request):
    # we put objects of type WebhookPayload into the update queue
    # Updates will trigger the webhook_update handler via the TypeHandler registered on startup
    body = await request.json()
    webhook_payload = WebhookPayload(**body)
    await app.application.update_queue.put(webhook_payload)
    return Response(status_code=HTTPStatus.OK)

# This is a simple healthcheck endpoint to verify that the bot is running
@app.get("/healthcheck")
async def health():
    return PlainTextResponse("The bot is still running fine :)", status_code=HTTPStatus.OK)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
