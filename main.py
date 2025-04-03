"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os
import re

from telegram import ForceReply, Update, Chat
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

from oneshotsdk import build_payload, get_endpoint, call_endpoint

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Define states for the conversation
ASKING_ADDRESS = 1

# Dictionary to store user wallet addresses
user_to_address = {}

# this is the endpoint id of the deployToken endpoint which will deploy ERC20 tokens
# you can find the endpoint id in the 1Shot endpoint dashboard
ENDPOINT_ID = os.getenv("ENDPOINT_ID", "deployToken_endpoint")

endpoint = get_endpoint(ENDPOINT_ID)

async def private_chat_only(update: Update) -> bool:
    """Helper function to check if the command is used in a private chat."""
    if update.message.chat.type != Chat.PRIVATE:
        await update.message.reply_text("This command is only available in private chat.")
        return False
    return True

def is_valid_ethereum_address(address: str) -> bool:
    """Check if the given string is a valid Ethereum address."""
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))

# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)

async def set_my_external_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate conversation and ask for the user's external address."""
    if not await private_chat_only(update):
        return ConversationHandler.END  # Exit if not in private chat

    await update.message.reply_text("What Ethereum address do you want to associate with your user ID?")
    return ASKING_ADDRESS  # Move to the next state

async def store_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the Ethereum wallet address if valid, otherwise ask again."""
    user_id = update.effective_user.id
    address = update.message.text.strip()

    if not is_valid_ethereum_address(address):
        await update.message.reply_text(
            "❌ Invalid Ethereum address! It must start with '0x' and be 42 characters long.\n"
            "Please enter a valid Ethereum address:"
        )
        return ASKING_ADDRESS  # Ask again

    # Save the valid address
    user_to_address[user_id] = address
    await update.message.reply_text(f"✅ Your Ethereum address has been saved: {address}")

    return ConversationHandler.END  # End the conversation

async def get_my_external_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow the user to retrieve their stored Ethereum address."""
    if not await private_chat_only(update):
        return  # Exit if not in private chat

    user_id = update.effective_user.id
    address = user_to_address.get(user_id, "⚠️ You have not set an Ethereum address yet.")

    await update.message.reply_text(f"💳 Your stored Ethereum address: {address}")

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with user details in private/group chats, and acknowledges commands in channels."""
    
    if update.message:  # Private chat or group
        user = update.effective_user
        if user.username:
            response = f"👤 Your username: @{user.username}\n🆔 Your user ID: {user.id}"
        else:
            response = "You don't have a username set."
        await update.message.reply_text(response)

    elif update.channel_post:  # Message from a channel
        if update.channel_post.text.startswith("/whoami"):
            await update.channel_post.reply_text("📢 This is a channel. I can't identify users here!")

async def chat_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Determines where the message is coming from."""
    chat_type = update.message.chat.type
    chat_id = update.message.chat.id
    chat_title = update.message.chat.title if update.message.chat.title else "N/A"

    if chat_type == "private":
        response = "📩 This is a private chat (DM) with the bot."
    elif chat_type == "group":
        response = f"👥 This is a group chat: {chat_title} (ID: {chat_id})"
    elif chat_type == "supergroup":
        response = f"🚀 This is a supergroup: {chat_title} (ID: {chat_id})"
    elif chat_type == "channel":
        response = f"📢 This message is from a channel: {chat_title} (ID: {chat_id})"
    else:
        response = "❓ Unknown chat type."

    await update.message.reply_text(response)

# Conversation states
ARG1, ARG2, ARG3, ARG4 = range(4)

async def deploy_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the first argument."""
    await update.message.reply_text("Lets build a token! What do you want to name your token?")
    return ARG1

async def get_arg1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store arg1 and ask for arg2."""
    context.user_data["arg1"] = update.message.text
    await update.message.reply_text("Great! What do you want the token symbol to be (users will see this next to their balance)?")
    return ARG2

async def get_arg2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store arg2 and ask for arg3."""
    context.user_data["arg2"] = update.message.text
    await update.message.reply_text("Awesome! What address should administer the token?")
    return ARG3

async def get_arg3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store arg3 and ask for arg4."""
    context.user_data["arg3"] = update.message.text
    await update.message.reply_text("Almost there, last question; how many tokens should be minted to the admin address?")
    return ARG4

async def get_arg4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store arg4, make the API call, and end the conversation."""
    context.user_data["arg4"] = update.message.text

    # Gather all arguments
    name, ticker, admin, premint = context.user_data["arg1"], context.user_data["arg2"], context.user_data["arg3"], context.user_data["arg4"]
    payload = build_payload(name=name, ticker=ticker, admin=admin, premint=premint)

    await update.message.reply_text(f"Deploying token: {payload}")

    execution = call_endpoint(endpoint.id, payload)

    await update.message.reply_text(f"Deploying {name} owned by {admin} with {premint} amount of {ticker}. Transaction Hash: {execution.transactionHash}")

    return ConversationHandler.END  # End the conversation

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("1Shot bot canceled.")
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token or set DISCORD_BOT_TOKEN as an environment variable
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for step-by-step input for deploying a token
    deploy_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("deploytoken", deploy_token_start)],
        states={
            ARG1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg1)],
            ARG2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg2)],
            ARG3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg3)],
            ARG4: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg4)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Define conversation handler for setting an external address
    address_setter_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setmyexternaladdress", set_my_external_address)],
        states={ASKING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_address)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("whereami", chat_context))
    application.add_handler(deploy_conv_handler)  # Add conversation handler
    application.add_handler(address_setter_conv_handler)  # Add conversation handler
    application.add_handler(CommandHandler("setmyexternaladdress", set_my_external_address))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_address))
    application.add_handler(CommandHandler("getmyexternaladdress", get_my_external_address))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()