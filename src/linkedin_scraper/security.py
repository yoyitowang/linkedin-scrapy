"""
Security utilities for the LinkedIn Job Scraper
"""
import os
import re
import logging
import random
import time
from typing import Dict, Any, Optional

# Set up logger
logger = logging.getLogger(__name__)

class SecurityManager:
    """
    Manages security aspects of the LinkedIn Job Scraper including:
    - Rate limiting
    - User agent rotation
    - Proxy management
    - Anti-detection measures
    """
    
    def __init__(self, debug: bool = False):
        """Initialize the security manager"""
        self.debug = debug
        self.request_count = 0
        self.last_request_time = time.time()
        self.user_agents = self._load_user_agents()
        
        # Configure logging
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    
    def _load_user_agents(self) -> list:
        """Load a list of user agents to rotate through"""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59'
        ]
    
    def get_request_headers(self) -> Dict[str, str]:
        """Get headers for the next request with rotated user agent"""
        # Increment request count
        self.request_count += 1
        
        # Select a random user agent
        user_agent = random.choice(self.user_agents)
        
        # Create headers that mimic a real browser
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
        }
        
        # Add a referer for requests after the first one
        if self.request_count > 1:
            headers['Referer'] = 'https://www.linkedin.com/jobs/'
        
        # Log headers in debug mode
        if self.debug:
            logger.debug(f"Generated headers with User-Agent: {user_agent}")
        
        return headers
    
    def apply_rate_limiting(self) -> None:
        """Apply rate limiting to avoid detection"""
        # Calculate time since last request
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Determine delay based on request count
        if self.request_count < 5:
            # Short delay for first few requests
            delay = random.uniform(1.0, 3.0)
        elif self.request_count < 15:
            # Medium delay
            delay = random.uniform(3.0, 5.0)
        else:
            # Longer delay after many requests
            delay = random.uniform(5.0, 8.0)
        
        # If we've made a request very recently, add extra delay
        if time_since_last < 1.0:
            delay += random.uniform(2.0, 4.0)
            
        # Log the delay in debug mode
        if self.debug:
            logger.debug(f"Applying rate limiting delay of {delay:.2f} seconds")
        
        # Apply the delay
        time.sleep(delay)
        
        # Update last request time
        self.last_request_time = time.time()
    
    def handle_security_challenge(self, response_url: str, status_code: int) -> Optional[Dict[str, Any]]:
        """
        Handle LinkedIn security challenges and blocks
        
        Returns:
            Dict with handling instructions or None if no challenge detected
        """
        # Check for security checkpoint
        if 'checkpoint' in response_url:
            logger.warning("LinkedIn security checkpoint detected!")
            return {
                'action': 'retry',
                'delay': random.uniform(60, 120),
                'message': 'Security checkpoint detected'
            }
        
        # Check for rate limiting (status code 429)
        if status_code == 429:
            logger.warning("LinkedIn rate limiting detected (429 status code)")
            return {
                'action': 'retry',
                'delay': random.uniform(300, 600),  # 5-10 minute delay
                'message': 'Rate limiting detected'
            }
        
        # Check for LinkedIn's anti-scraping measures (status code 999)
        if status_code == 999:
            logger.warning("LinkedIn anti-scraping triggered (999 status code)")
            return {
                'action': 'retry',
                'delay': random.uniform(120, 240),  # 2-4 minute delay
                'message': 'Anti-scraping measures detected'
            }
        
        # Check for other client errors
        if 400 <= status_code < 500:
            logger.warning(f"Client error: {status_code}")
            return {
                'action': 'retry',
                'delay': random.uniform(30, 60),
                'message': f'Client error {status_code}'
            }
        
        # Check for server errors
        if 500 <= status_code < 600:
            logger.warning(f"Server error: {status_code}")
            return {
                'action': 'retry',
                'delay': random.uniform(60, 120),
                'message': f'Server error {status_code}'
            }
        
        # No security challenge detected
        return None
    
    def is_captcha_page(self, response_text: str) -> bool:
        """Check if the response contains a CAPTCHA challenge"""
        captcha_indicators = [
            'captcha', 'CAPTCHA', 
            'security verification', 
            'verify you are a human',
            'unusual activity',
            'automated access',
            'prove you\'re not a robot'
        ]
        
        for indicator in captcha_indicators:
            if indicator in response_text:
                logger.warning(f"CAPTCHA detected: Found '{indicator}' in response")
                return True
        
        return False
    
    def sanitize_input(self, input_text: str) -> str:
        """Sanitize input to prevent injection attacks"""
        if not input_text:
            return ""
            
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>\'";]', '', input_text)
        
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
            
        return sanitized