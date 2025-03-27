"""
Scrapy settings for linkedin_scraper project
"""

BOT_NAME = 'linkedin_scraper'

SPIDER_MODULES = ['linkedin_scraper.spiders']
NEWSPIDER_MODULE = 'linkedin_scraper.spiders'

# Crawl responsibly by identifying yourself on the user agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Obey robots.txt rules - set to False for LinkedIn
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 1

# Configure a delay for requests to avoid being blocked
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'linkedin_scraper.middlewares.LinkedinScraperDownloaderMiddleware': 543,
}

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    'linkedin_scraper.middlewares.LinkedinScraperSpiderMiddleware': 543,
}

# Configure item pipelines
ITEM_PIPELINES = {
    'linkedin_scraper.pipelines.LinkedinJobPipeline': 300,
}

# Enable and configure HTTP caching
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
FEED_EXPORT_ENCODING = 'utf-8'