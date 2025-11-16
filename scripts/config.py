
#!/usr/bin/env python3
"""
Configuration settings for the Biotech News Aggregator
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for the news aggregator"""
    
    # QuoteAPI Settings (for ASX data)
    QUOTEAPI_USERNAME = os.getenv('QUOTEAPI_USERNAME')
    QUOTEAPI_PASSWORD = os.getenv('QUOTEAPI_PASSWORD')
    QUOTEAPI_APP_ID = os.getenv('QUOTEAPI_APP_ID')
    QUOTEAPI_BASE_URL = "https://quoteapi.com/api/v5/symbols"

    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

