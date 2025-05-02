import os

from uxly_1shot_client import AsyncClient

# its handy to set your API key and secret with environment variables
API_KEY = os.getenv("ONESHOT_API_KEY")
API_SECRET = os.getenv("ONESHOT_API_SECRET")
BUSINESS_ID = os.getenv("ONESHOT_BUSINESS_ID") 
                        
oneshot_client = AsyncClient(api_key=API_KEY, api_secret=API_SECRET)