"""
Middlewares for the LinkedIn Job Scraper
"""

from scrapy import signals
from scrapy.http import HtmlResponse
import time
import random
import logging
from .security import SecurityManager


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
            # Check if the spider has reached its job limit before yielding
            if hasattr(spider, 'reached_job_limit') and spider.reached_job_limit:
                # Only yield items, not requests
                if not hasattr(i, 'callback'):
                    yield i
            else:
                yield i

    def process_spider_exception(self, response, exception, spider):
        pass

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class LinkedinScraperDownloaderMiddleware:
    """Downloader middleware for LinkedIn Job Scraper with enhanced security"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.security_manager = None
        self.request_count = 0

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        """Process each request before it's sent to LinkedIn"""
        # Skip processing if the spider has reached its job limit
        if hasattr(spider, 'reached_job_limit') and spider.reached_job_limit:
            self.logger.info("Job limit reached, canceling request")
            return HtmlResponse(
                url=request.url,
                status=200,
                body=b'<html><body><h1>Job limit reached</h1></body></html>',
                encoding='utf-8',
                request=request
            )
            
        # Apply rate limiting
        self.security_manager.apply_rate_limiting()
        
        # Get headers with rotated user agent
        headers = self.security_manager.get_request_headers()
        
        # Update request headers
        for key, value in headers.items():
            request.headers[key] = value
        
        # Add cookies if available
        if hasattr(spider, 'cookies') and spider.cookies:
            for cookie_name, cookie_value in spider.cookies.items():
                request.cookies[cookie_name] = cookie_value
        
        # Increment request counter
        self.request_count += 1
        
        # Add longer delays after every 10 requests to avoid patterns
        if self.request_count % 10 == 0:
            spider.logger.info(f"Adding extra delay after {self.request_count} requests")
            time.sleep(random.uniform(10, 20))
        
        return None

    def process_response(self, request, response, spider):
        """Process each response from LinkedIn"""
        # Skip processing if the spider has reached its job limit
        if hasattr(spider, 'reached_job_limit') and spider.reached_job_limit:
            return response
            
        # Check for security challenges
        security_action = self.security_manager.handle_security_challenge(
            response.url, response.status
        )
        
        if security_action:
            spider.logger.warning(f"Security challenge detected: {security_action['message']}")
            spider.logger.info(f"Waiting {security_action['delay']:.1f} seconds before retry")
            
            # Apply the recommended delay
            time.sleep(security_action['delay'])
            
            # If action is to retry, return the original request
            if security_action['action'] == 'retry':
                # Clear cookies and get new headers for retry
                request.cookies.clear()
                headers = self.security_manager.get_request_headers()
                for key, value in headers.items():
                    request.headers[key] = value
                
                # Don't retry too many times
                retry_count = request.meta.get('retry_count', 0) + 1
                if retry_count <= 3:  # Maximum 3 retries
                    request.meta['retry_count'] = retry_count
                    spider.logger.info(f"Retrying request (attempt {retry_count}/3)")
                    return request
        
        # Check for CAPTCHA
        if self.security_manager.is_captcha_page(response.text):
            spider.logger.error("CAPTCHA detected! Scraping may be blocked.")
            # You could implement CAPTCHA solving here or notify the user
            
        return response

    def process_exception(self, request, exception, spider):
        """Handle exceptions during requests"""
        # Skip processing if the spider has reached its job limit
        if hasattr(spider, 'reached_job_limit') and spider.reached_job_limit:
            return None
            
        spider.logger.error(f"Request exception: {exception}")
        
        # Add delay before retry
        retry_delay = random.uniform(5.0, 10.0)
        spider.logger.info(f"Waiting {retry_delay:.1f} seconds before retry")
        time.sleep(retry_delay)
        
        # Clear cookies for retry
        request.cookies.clear()
        
        # Don't retry too many times
        retry_count = request.meta.get('retry_count', 0) + 1
        if retry_count <= 3:  # Maximum 3 retries
            request.meta['retry_count'] = retry_count
            spider.logger.info(f"Retrying request after exception (attempt {retry_count}/3)")
            return request
        
        return None

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)
        
        # Initialize security manager with spider's debug setting
        debug_mode = getattr(spider, 'debug', False)
        self.security_manager = SecurityManager(debug=debug_mode)