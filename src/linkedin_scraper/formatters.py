"""
Custom log formatters for the LinkedIn Job Scraper
"""

import logging
import re
from scrapy.logformatter import LogFormatter

class LinkedInLogFormatter(LogFormatter):
    """
    Custom log formatter to filter out detailed item data when debug mode is disabled
    """
    
    def scraped(self, item, response, spider):
        """
        Customizes the log output for scraped items
        """
        if not spider.debug:
            # When debug is off, just log a simple message without the item details
            # Updated to use the correct field names: 'title' and 'companyName'
            return {
                'level': logging.INFO,
                'msg': f"Scraped job: {item.get('title', '')} at {item.get('companyName', '')}"
            }
        
        # In debug mode, use the default behavior
        return super().scraped(item, response, spider)
    
    def format(self, result):
        """
        Override format method to filter out certain log messages when debug is off
        """
        if not result.get('msg'):
            return result
        
        # Check if this is a spider instance with debug attribute
        spider = result.get('spider')
        debug_mode = getattr(spider, 'debug', True)  # Default to True if not found
        
        if not debug_mode:
            # Filter out detailed data dumps from logs
            msg = result['msg']
            
            # Skip detailed data dumps (like the job description HTML)
            if isinstance(msg, str) and len(msg) > 500:
                # If it's a long string, it's probably a data dump
                result['msg'] = "Large data item processed (detailed output suppressed)"
            
            # Filter out item dictionaries
            if isinstance(msg, str) and msg.startswith('{') and ': ' in msg:
                result['msg'] = "Item processed (detailed output suppressed)"
        
        return result