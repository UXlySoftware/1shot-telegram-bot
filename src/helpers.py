from telegram import Chat, Update
from telegram.ext import ContextTypes, ConversationHandler

from oneshotsdk import (
    EndpointCreationPayload, 
    get_escrow_wallet,
    make_endpoint
)
from objects import Blockchains, ConversationState

import re
import os
import json

COINUCOPIA_BASE_URL = os.getenv("COINUCOPIA_BASE_URL") + "/1shot"

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

def get_token_mint_endpoint_creation_payload(chain_id: str, contract_address: str, name: str) -> EndpointCreationPayload:
    mint_endpoint_payload = {
        "chain": chain_id,
        "contractAddress": contract_address,
        "escrowWalletId": get_chain_escrow_wallet_id(chain_id),
        "name": f"{name} Token mint",
        "description": f"This calls the mint() method on the {name} ERC20 contract",
        "functionName": "mint",
        "callbackUrl": f"{COINUCOPIA_BASE_URL}",
        "inputs": [
            {
                "name": "to",
                "type": "address",
                "index": 0
            },
            {
                "name": "amount",
                "type": "uint",
                "index": 1
            },
        ]
    }

    return EndpointCreationPayload(**mint_endpoint_payload)

async def make_token_mint_endpoint(chain_id: str, contract_address: str, name: str) -> str:
    mint_endpoint_payload = get_token_mint_endpoint_creation_payload(str(chain_id), contract_address, name)
    endpoint = make_endpoint(mint_endpoint_payload.model_dump(by_alias=True))
    return endpoint.id

def get_token_grant_admin_endpoint_creation_payload(chain_id: str, contract_address: str, name: str) -> EndpointCreationPayload:
    mint_endpoint_payload = {
        "chain": chain_id,
        "contractAddress": contract_address,
        "escrowWalletId": get_chain_escrow_wallet_id(chain_id),
        "name": f"{name} Token Grant Admin",
        "description": f"This calls the grantRole() method on the {name} ERC20 contract",
        "functionName": "grantRole",
        "callbackUrl": f"{COINUCOPIA_BASE_URL}",
        "inputs": [
            {
                "name": "role",
                "type": "bytes",
                "typeSize": 32,
                "index": 0,
                "value": "0x0000000000000000000000000000000000000000000000000000000000000000"
            },
            {
                "name": "account",
                "type": "address",
                "index": 1
            },
        ]
    }

    return EndpointCreationPayload(**mint_endpoint_payload)

async def make_token_grant_admin_endpoint(chain_id: str, contract_address: str, name: str) -> str:
    grant_admin_endpoint_payload = get_token_grant_admin_endpoint_creation_payload(str(chain_id), contract_address, name)
    endpoint = make_endpoint(grant_admin_endpoint_payload.model_dump(by_alias=True))
    return endpoint.id

def get_token_deployer_endpoint_creation_payload(chain_id: str, contract_address: str) -> EndpointCreationPayload:
    mint_endpoint_payload = {
        "chain": chain_id,
        "contractAddress": contract_address,
        "escrowWalletId": get_chain_escrow_wallet_id(chain_id),
        "name": f"{get_chain_name_from_chain_id(chain_id)} Token Deployer",
        "description": f"This deploys ERC20 tokens on {get_chain_name_from_chain_id(chain_id)}",
        "functionName": "deployToken",
        "callbackUrl": f"{COINUCOPIA_BASE_URL}",
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
        ]
    }

    return EndpointCreationPayload(**mint_endpoint_payload)
