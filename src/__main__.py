"""
Main entry point for the LinkedIn Job Scraper Apify Actor.
"""

import asyncio
from .main import main

# Run the main coroutine
asyncio.run(main())