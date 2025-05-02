import os

from pydantic import BaseModel, Field
from typing import Optional

from enum import Enum

# extends this to include the new transaction types specific to your bot's use case
class TxType(Enum):
    TOKEN_CREATION = 0
    ADMIN_ADDED = 1
    TOKENS_MINTED = 2
    TOKENS_TRANSFERRED = 3

class TransactionMemo(BaseModel):
    tx_type: TxType = Field(..., description="The kind of transaction that was executed."
    )
    associated_user_id: int
    note_to_user: Optional[str] = Field(None, description="Info to relay to the associated_user")

# user enums to define the different states of your conversation flows
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