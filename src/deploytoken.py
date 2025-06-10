import os
import logging

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler
)
from telegram.constants import ParseMode
from telegram.helpers import mention_html

logger = logging.getLogger(__name__)

from oneshot import (
    oneshot_client,
    BUSINESS_ID
)

from helpers import (
    is_nonnegative_integer, 
    canceler, 
    convert_to_wei
)
from objects import (
    TransactionMemo,
    TxType,
    TokenInfo,
    ConversationState, 
)

async def deploy_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user what name they want to give to their token."""

    await update.callback_query.answer()  # Acknowledge the callback query
    await update.callback_query.edit_message_text(text="What do you want to name your token?")
    return ConversationState.TOKEN_NAMING

async def get_naming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store token name and ask for the token ticker (symbol)."""
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Great! What do you want the token symbol to be (users will see this next to their balance)?")
    return ConversationState.TOKEN_TICKER

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the token ticker and ask for a description."""
    context.user_data["ticker"] = update.message.text
    await update.message.reply_text("Please provide a description for your token:")
    return ConversationState.TOKEN_DESCRIPTION

async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the description and ask the user to upload an image."""
    context.user_data["description"] = update.message.text
    await update.message.reply_text("Great! Please upload an image for the token (e.g., logo).")
    return ConversationState.TOKEN_IMAGE

async def get_premint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the image and ask for how many tokens to premint."""
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data["image"] = file_id
        await update.message.reply_text(
            "Awesome! How many tokens should be minted to the admin address (must be an integer)?"
        )
        return ConversationState.TOKEN_PREMINT
    else:
        await update.message.reply_text("❌ Please upload a valid image.")
        return ConversationState.TOKEN_IMAGE

async def finalize_token_deployment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the admin address, make the API call, and end the conversation."""
    premint = update.message.text
    if not is_nonnegative_integer(premint):
        await update.message.reply_text(
            "❌ Invalid input! Please enter a positive integer for the premint amount:"
        )
        return ConversationState.TOKEN_PREMINT

    # Gather all arguments
    chain_id = '11155111' # example is hardcoded for the Sepolia testnet
    name = context.user_data["name"]
    ticker = context.user_data["ticker"]
    description = context.user_data["description"]
    image_file_id = context.user_data.get("image", None)  # Optional, in case no image was uploaded
    
    # Its better to store escrow wallet ids as enironment variables or in your apps database
    # but we will look it up to demonstrate how to fetch wallets from 1Shot API
    # Note for this demo to work, make sure there is only 1 wallet in your organization for the Sepolia network
    wallet = await oneshot_client.wallets.list(BUSINESS_ID, {"chain_id": chain_id})

    contract_method = await oneshot_client.contract_methods.list(
        business_id=BUSINESS_ID,
        params={"page": 1, "page_size": 10, "chain_id": "11155111", "name": "1Shot Demo Sepolia Token Deployer"}
    )

    # This message will come back to the bot when the transaction is executed
    # We can use the info to figure out how to react
    # since we are using a pydantic dataclass, we can validate the content
    token_info = TokenInfo(
        name=name,
        ticker=ticker,
        description=description,
        image_file_id=image_file_id
    )
    memo = TransactionMemo(
        tx_type=TxType.TOKEN_CREATION.value,
        associated_user_id=update.effective_user.id,
        note_to_user=token_info.model_dump_json()
    )

    transaction = await oneshot_client.contract_methods.execute(
        contract_method_id=contract_method.response[0].id,
        params={
            "name": name,
            "ticker": ticker,
            "admin": wallet.response[0].account_address,
            "premint": convert_to_wei(premint),
        },
        memo=memo.model_dump_json()
    )
    logger.info(f"Token creation transaction executed: {transaction.id}")

    buttons = [[InlineKeyboardButton(text="Back", callback_data="start")]]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "✅ Your token is being deployed! You will be notified once it's ready.", reply_markup=keyboard
    )

    context.user_data[ConversationState.START_OVER] = True

    return ConversationState.START_ROUTES # End the conversation

async def successful_token_deployment(token_address: str, memo: TransactionMemo, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify the user that their token has been created."""
    token_info = TokenInfo.model_validate_json(memo.note_to_user)

    success_message = (
        f"<code>New Coin Created!</code>\n\n"
        f"<b>Name:</b> {token_info.name}\n"
        f"<b>Ticker:</b> {token_info.ticker}\n"
        f"<b>Description:</b> {token_info.description}\n"
        f"Address: <a href='https://sepolia.etherscan.io/token/{token_address}'>{token_address}</a>\n"
    )

    await context.bot.send_photo(
        chat_id=memo.associated_user_id, 
        photo=token_info.image_file_id, 
        caption=success_message, 
        parse_mode=ParseMode.HTML
    )

def get_token_deployment_conversation_handler() -> ConversationHandler:
    """Create and return the conversation handler for token deployment."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(deploy_token_start, pattern="^deploytoken$")
            ],
        states={
            ConversationState.TOKEN_NAMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_naming)],
            ConversationState.TOKEN_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            ConversationState.TOKEN_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_image)],
            ConversationState.TOKEN_IMAGE: [MessageHandler(filters.PHOTO & ~filters.COMMAND, get_premint)],
            ConversationState.TOKEN_PREMINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_token_deployment)],
        },
        fallbacks=[CommandHandler("cancel", canceler)],
        map_to_parent={
            ConversationState.START_ROUTES: ConversationState.START_ROUTES,
            ConversationHandler.END: ConversationHandler.END
        }
    )
