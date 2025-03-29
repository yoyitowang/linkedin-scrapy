"""
Utility functions for the LinkedIn Job Scraper
"""
import re
from datetime import datetime

def clean_html(html_text):
    """Clean HTML content and extract readable text"""
    if not html_text:
        return ""
    
    try:
        # First, extract just the main content section which contains the job description
        main_content_match = re.search(r'<div class="description__text[^>]*>(.*?)</div>\s*</section>', html_text, re.DOTALL)
        if main_content_match:
            html_text = main_content_match.group(1)
        
        # Remove all buttons and UI elements
        html_text = re.sub(r'<button.*?</button>', '', html_text, flags=re.DOTALL)
        html_text = re.sub(r'<icon.*?</icon>', '', html_text, flags=re.DOTALL)
        
        # Remove script and style elements
        html_text = re.sub(r'<script.*?>.*?</script>', '', html_text, flags=re.DOTALL)
        html_text = re.sub(r'<style.*?>.*?</style>', '', html_text, flags=re.DOTALL)
        
        # Replace common HTML elements with text formatting
        html_text = re.sub(r'<br\s*/?>|<br\s*/?>', '\n', html_text)
        html_text = re.sub(r'<li.*?>', '• ', html_text)
        html_text = re.sub(r'</li>', '\n', html_text)
        html_text = re.sub(r'</(p|div|h\d|ul|ol)>', '\n', html_text)
        html_text = re.sub(r'<(p|div|h\d|ul|ol)[^>]*>', '', html_text)
        
        # Remove any remaining HTML tags
        html_text = re.sub(r'<[^>]*>', '', html_text)
        
        # Handle special HTML entities
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')
        html_text = html_text.replace('&quot;', '"')
        html_text = html_text.replace('&nbsp;', ' ')
        
        # Fix multiple consecutive newlines
        html_text = re.sub(r'\n{3,}', '\n\n', html_text)
        
        # Fix multiple spaces
        html_text = re.sub(r' {2,}', ' ', html_text)
        
        return html_text.strip()
    except Exception:
        # If all else fails, just return the original with tags stripped
        return re.sub(r'<[^>]*>', '', html_text).strip()

def clean_text(text):
    """Clean text by removing extra whitespace"""
    if not text:
        return ""
    return ' '.join(text.split())

def format_datetime(date_value):
    """Format date to ISO format (YYYY-MM-DDTHH:MM:SS)"""
    if not date_value:
        return None
        
    try:
        # If it's already a datetime object
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%dT%H:%M:%S')
            
        # If it's already in ISO format
        if isinstance(date_value, str) and 'T' in date_value:
            # Ensure it's properly formatted
            dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # If it's a timestamp (integer)
        if isinstance(date_value, (int, float)):
            dt = datetime.fromtimestamp(date_value / 1000)  # Convert milliseconds to seconds
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
            
        # If it's a relative date string, use current date
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return None