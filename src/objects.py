import os

from pydantic import BaseModel, Field
from typing import Optional

from enum import Enum

# Pydantic data classes and Enums are useful for creating transaction memos that can be validated 

# extend this to include the new transaction types specific to your bot's use case
# switch on the type for dynamic handling logic like messaging your user once their token has been mined
class TxType(Enum):
    TOKEN_CREATION = 0
    ADMIN_ADDED = 1
    TOKENS_MINTED = 2
    TOKENS_TRANSFERRED = 3

# use the memo field when you execute a transaction to include context on the callback to your bot
class TransactionMemo(BaseModel):
    tx_type: TxType = Field(..., description="The kind of transaction that was executed.") 
    associated_user_id: int = Field(..., description="The user id of the user that executed the transaction.")
    note_to_user: Optional[str] = Field(None, description="Arbitrary info to relay to the associated_user")

# we'll use this to store token information so we can send the user a message when the token is created
class TokenInfo(BaseModel):
    name: str = Field(..., description="The name of the token.")
    ticker: str = Field(..., description="The ticker symbol for the token.")
    description: str = Field(..., description="A description of the token.")
    image_file_id: str = Field(..., description="The file id of the token image.")

# user enums to define the different states of your Telegram bot conversation flows
class ConversationState(Enum):
    START_ROUTES = 1
    ASKING_ADDRESS = 2
    TOKEN_CHAIN = 3
    TOKEN_NAMING = 4
    TOKEN_TICKER = 5
    TOKEN_DESCRIPTION = 6
    TOKEN_IMAGE = 7
    TOKEN_PREMINT = 8
    TOKEN_ADMIN = 9
    GET_TOKENS = 10
    MANAGE_TOKEN = 11
    SENDER_LIST = 12
    CHAT_TRIGGER_AMOUNT=13
    START_OVER = 999