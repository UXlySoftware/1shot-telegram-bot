# 1Shot Telegram Bot Demo

This is a simple Telegram bot that shows how to implement a conversation flow which will call 1Shot to deploy an ERC20 token. 

## 1. Register a Telegram Bot

Start by using the [@BotFather](https://telegram.me/BotFather) to register a new Telegram bot and getting a Telegram API Token. 

## 2. Create a 1Shot API Account

Log into 1Shot and create a new API key and secret from the [API Keys](https://app.1shotapi.com/api-keys) page. You'll need both the client ID and
secret for your bot. 

Also, go to the [Organizations page](https://app.1shotapi.com/organizations) and click on the "Details" button of your org. Grab the business ID from the url. 

## 3. Build the bot Docker image

Clone this repo and build the bot container image:

```sh
docker build -t bot .
```

## 4. Run the bot container

Gather you Telegram bot token, API key and secret, business id, and endpoint id to run the bot container: 

```sh
docker run -d --rm --name bot -e TELEGRAM_BOT_TOKEN=<get-a-token-from-discord> -e API_KEY=<1Shot-API-Key> -e API_SECRET=<1Shot-API-Secret> -e BUSINESS_ID=<Your-1Shot-Busines-ID> -e ENDPOINT_ID=<deployToken-endpoint-id> bot
```

# 5. Use the bot to deploy a token

Use the /deploytoken command to initiate a conversational flow to deploy a new token.