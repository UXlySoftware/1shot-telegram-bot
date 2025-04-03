import os
import time
import requests
import json
from threading import Lock

from pydantic import BaseModel
from typing import List, Optional

API_BASE_URL = "https://api.1shotapi.com/v0"

# API credentials (replace with your actual key and secret)
API_KEY = os.getenv("API_KEY", "your_api_key")
API_SECRET = os.getenv("API_SECRET", "your_api_secret")
BUSINESS_ID = os.getenv("BUSINESS_ID", "your_api_secret")  # Replace with the business ID


class TokenManager:
    """Manages the API access token, refreshing it automatically when expired."""
    
    def __init__(self):
        self._token = None
        self._expires_at = 0
        self._lock = Lock()
    
    def _fetch_token(self):
        """Fetch a new bearer token from the API."""
        url = f"{API_BASE_URL}/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": API_KEY,
            "client_secret": API_SECRET,
        }
        response = requests.post(url, headers=headers, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            self._token = data["access_token"]
            self._expires_at = time.time() + data["expires_in"] - 10  # Refresh a bit before expiration
        else:
            raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

    def get_token(self):
        """Return a valid token, refreshing it if necessary."""
        with self._lock:
            if not self._token or time.time() >= self._expires_at:
                self._fetch_token()
            return self._token


# Instantiate the token manager
token_manager = TokenManager()


class EndpointParam(BaseModel):
    arraySize: Optional[int]
    description: str
    id: str
    index: int
    isArray: bool
    name: str
    structId: str
    type: str
    typeSize: Optional[int]
    typeSize2: Optional[int]
    typeStruct: Optional[str]
    typeStructId: Optional[str]
    value: Optional[str]


class Endpoint(BaseModel):
    businessId: str
    callbackUrl: Optional[str]
    chain: int
    contractAddress: str
    created: int
    description: str
    escrowWalletId: str
    functionName: str
    id: str
    name: str
    nativeTransaction: bool
    params: List[EndpointParam]
    payable: bool
    publicKey: Optional[str]
    updated: int


class ExecutionResponse(BaseModel):
    apiCredentialId: str
    apiKey: str
    chain: int
    chainTransactionId: str
    completedTimestamp: Optional[int]  # Can be None
    contractAddress: str
    createdTimestamp: int
    deleted: bool
    functionName: str
    id: str
    name: str
    status: str
    transactionHash: Optional[str]  # Can be None
    transactionId: str
    updatedTimestamp: int
    userId: Optional[str]  # Can be None


def get_endpoints():
    """Fetch available transaction endpoints with automatic auth token handling."""
    url = f"{API_BASE_URL}/business/{BUSINESS_ID}/transactions"
    headers = {"Authorization": f"Bearer {token_manager.get_token()}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        transactions = response.json()["response"]
        return [Endpoint(**transaction) for transaction in transactions]
    else:
        raise Exception(f"Failed to fetch transactions: {response.status_code}, {response.text}")


def get_endpoint(transaction_id):
    """Fetch a specific transaction endpoint with automatic auth token handling."""
    url = f"{API_BASE_URL}/transactions/{transaction_id}"
    headers = {"Authorization": f"Bearer {token_manager.get_token()}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return Endpoint(**response.json())
    else:
        raise Exception(f"Failed to fetch transaction: {response.status_code}, {response.text}")


def call_endpoint(endpoint_id: str, params: dict):
    """Call a specific transaction endpoint with automatic auth token handling."""
    url = f"{API_BASE_URL}/transactions/{endpoint_id}/execute"
    headers = {
        "Authorization": f"Bearer {token_manager.get_token()}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(params))
    
    if response.status_code == 200:
        return ExecutionResponse(**response.json())
    else:
        raise Exception(f"Failed to execute transaction: {response.status_code}, {response.text}")


def build_payload(**kwargs) -> dict:
    """Builds a payload dictionary from keyword arguments."""
    payload = {"params": {}}
    
    for key, value in kwargs.items():
        payload["params"][key] = str(value) if value is not None else "default_value"
    
    return payload
