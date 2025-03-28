"""
Middlewares for the LinkedIn Job Scraper
"""

from scrapy import signals
from scrapy.http import HtmlResponse
import time
import random


class LinkedinScraperSpiderMiddleware:
    """Spider middleware for LinkedIn Job Scraper"""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        pass

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class LinkedinScraperDownloaderMiddleware:
    """Downloader middleware for LinkedIn Job Scraper"""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Add random delay to avoid detection
        time.sleep(random.uniform(1.0, 5.0))
        
        # Add headers to mimic browser behavior
        request.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
        })
        
        return None

    def process_response(self, request, response, spider):
        # Check for LinkedIn's anti-scraping measures
        if response.status == 999:
            spider.logger.warning("LinkedIn anti-scraping triggered! Retrying after delay...")
            time.sleep(random.uniform(60, 120))  # Longer delay for retry
            return request
            
        # Check for login redirects
        if response.url.startswith('https://www.linkedin.com/checkpoint/'):
            spider.logger.warning("LinkedIn security checkpoint detected!")
            
        return response

    def process_exception(self, request, exception, spider):
        spider.logger.error(f"Request exception: {exception}")
        time.sleep(random.uniform(5.0, 10.0))
        return request

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)