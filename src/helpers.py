from telegram import Chat, Update
from telegram.ext import ContextTypes, ConversationHandler

from oneshot import (
    oneshot_client,
    BUSINESS_ID
)

from objects import ConversationState

import re
import os
from typing import Dict, Any

CALLBACK_URL = os.getenv("TUNNEL_BASE_URL") + "/1shot"

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
    await update.message.reply_text("Coinucopia task canceled.")
    context.user_data[ConversationState.START_OVER] = False
    return ConversationHandler.END


def get_token_deployer_endpoint_creation_payload(chain_id: str, contract_address: str, escrow_wallet_id: str) -> Dict[str, str]:
     return {
        "chain": chain_id,
        "contractAddress": contract_address,
        "escrowWalletId": escrow_wallet_id,
        "name": f"1Shot Demo Sepolia Token Deployer",
        "description": f"This deploys ERC20 tokens on the Sepolia testnet.",
        "functionName": "deployToken",
        "callbackUrl": f"{CALLBACK_URL}",
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