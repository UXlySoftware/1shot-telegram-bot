from telegram import Chat, Update
from telegram.ext import ContextTypes, ConversationHandler

from fastapi import Request, HTTPException

from oneshot import (
    oneshot_client,
)

from objects import ConversationState

from uxly_1shot_client import verify_webhook

import re
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Python doesn't have a built-in BigInt type, so we use a string to represent large integers
def convert_to_wei(amount: str) -> str:
    """Convert a string amount to string wei (1 ether = 10^18 wei)."""
    try:
        value = int(amount)
        if value < 0:
            raise ValueError("Negative value")
        return str(amount) + "000000000000000000"  # Append 18 zeros to convert to wei
    except ValueError:
        raise ValueError("Invalid value: must be a non-negative integer.")

# handy function to check if a user entered a non-neggative value
def is_nonnegative_integer(value: str) -> bool:
    """Check if the given string represents a positive integer."""
    try:
        return int(value) >= 0
    except ValueError:
        return False

# handy function to check if a user entered a valid Ethereum address
def is_valid_ethereum_address(address: str) -> bool:
    """Check if the given string is a valid Ethereum address."""
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))

# Can be used as a general fallback function to end conversation flows
async def canceler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("bye 👋")
    context.user_data[ConversationState.START_OVER] = False
    return ConversationHandler.END


def get_token_deployer_endpoint_creation_payload(chain_id: str, contract_address: str, escrow_wallet_id: str, callback: str) -> Dict[str, str]:
     return {
        "chain_id": chain_id,
        "contractAddress": contract_address,
        "walletId": escrow_wallet_id,
        "name": "1Shot Demo Sepolia Token Deployer",
        "description": "This deploys ERC20 tokens on the Sepolia testnet.",
        "functionName": "deployToken",
        "callbackUrl": f"{callback}",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "admin",
                "type": "address",
                "index": 0,
            },
            {
                "name": "name",
                "type": "string",
                "index": 1
            },
            {
                "name": "ticker",
                "type": "string",
                "index": 2
            },
            {
                "name": "premint",
                "type": "uint",
                "index": 3
            }
        ],
        "outputs": []
    }

# example of a wrapper class to handle webhook verification with FastAPI
# rather than looking up the public key from 1Shot API each time, you could store it in a database or cache
class webhookAuthenticator:
    # you could do something with the constructor like set up a database connection
    def __init__(self):
        logger.info("Webhook Authenticator initialized.")

    async def __call__(self, request: Request):
        try:
            # Extract the required fields from the request
            body = await request.json()  # Raw request body

            if not body["signature"]:
                raise HTTPException(status_code=400, detail="Signature field missing")
            
            # look up the contract method endpoint that generated the callback and get the public key
            # in a production application, store the public key in a database or cache for faster access
            contract_method = await oneshot_client.contract_methods.get(
                contract_method_id=body["data"]["transactionId"],
            )

            if not contract_method.public_key:
                raise HTTPException(status_code=400, detail="Public key not found")

            # Verify the signature with the public key you stored corresponding to the transaction ID
            is_valid = verify_webhook(
                body=body,
                signature=body["signature"],
                public_key=contract_method.public_key
            )

            if not is_valid:
                raise HTTPException(status_code=403, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            raise HTTPException(status_code=500, detail=f"Internal error: {e}")