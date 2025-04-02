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

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

from oneshot import build_payload, get_bearer_token, get_endpoint, call_endpoint

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# this is the endpoint id of the deployToken endpoint which will deploy ERC20 tokens
# you can find the endpoint id in the 1Shot endpoint dashboard
ENDPOINT_ID = os.getenv("ENDPOINT_ID", "deployToken_endpoint")

access_token = get_bearer_token()
endpoint = get_endpoint(access_token, ENDPOINT_ID)

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

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with the username of the user calling the command."""
    user = update.effective_user
    if user.username:
        await update.message.reply_text(f"Your username is @{user.username}; your user id is {user.id}.")
    else:
        await update.message.reply_text("You don't have a username set.")

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

    execution = call_endpoint(access_token, endpoint.id, payload)

    await update.message.reply_text(f"Deploying {name} owned by {admin} with {premint} amount of {ticker}. Transaction Hash: {execution.transactionHash}")

    return ConversationHandler.END  # End the conversation

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Token deployment canceled.")
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token or set DISCORD_BOT_TOKEN as an environment variable
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Conversation handler for step-by-step input
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("deploytoken", deploy_token_start)],
        states={
            ARG1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg1)],
            ARG2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg2)],
            ARG3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg3)],
            ARG4: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arg4)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(conv_handler)  # Add conversation handler

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()