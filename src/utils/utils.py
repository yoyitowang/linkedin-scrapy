"""
Utility functions for the LinkedIn Job Scraper
"""
import re
from datetime import datetime, timedelta

def clean_html(html_text):
    """
    Clean HTML content by removing scripts, styles, and converting <br> to newlines
    
    Args:
        html_text: HTML content to clean
        
    Returns:
        Cleaned HTML text
    """
    if not html_text:
        return ""
    
    # Remove script and style elements
    html_text = re.sub(r'<script.*?>.*?</script>', '', html_text, flags=re.DOTALL)
    html_text = re.sub(r'<style.*?>.*?</style>', '', html_text, flags=re.DOTALL)
    
    # Convert <br> to newlines for better readability in plain text
    html_text = re.sub(r'<br\s*/?>|<br\s*/?>', '\n', html_text)
    
    return html_text.strip()

def clean_text(text):
    """
    Clean text by removing extra whitespace
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    return ' '.join(text.split())

def parse_relative_time(relative_time_text):
    """
    Parse relative time text (like "5 hours ago", "2 days ago") 
    and return an estimated datetime
    
    Args:
        relative_time_text: Text describing relative time
        
    Returns:
        datetime object or None if parsing fails
    """
    if not relative_time_text:
        return None
        
    now = datetime.now()
    relative_time_text = relative_time_text.lower().strip()
    
    # Match patterns like "5 hours ago", "2 days ago", "1 week ago", etc.
    minutes_match = re.search(r'(\d+)\s+minute', relative_time_text)
    hours_match = re.search(r'(\d+)\s+hour', relative_time_text)
    days_match = re.search(r'(\d+)\s+day', relative_time_text)
    weeks_match = re.search(r'(\d+)\s+week', relative_time_text)
    months_match = re.search(r'(\d+)\s+month', relative_time_text)
    
    if minutes_match:
        minutes = int(minutes_match.group(1))
        return now - timedelta(minutes=minutes)
    elif hours_match:
        hours = int(hours_match.group(1))
        return now - timedelta(hours=hours)
    elif days_match:
        days = int(days_match.group(1))
        return now - timedelta(days=days)
    elif weeks_match:
        weeks = int(weeks_match.group(1))
        return now - timedelta(weeks=weeks)
    elif months_match:
        months = int(months_match.group(1))
        # Approximate a month as 30 days
        return now - timedelta(days=30*months)
    elif "just now" in relative_time_text or "just posted" in relative_time_text:
        return now
    elif "yesterday" in relative_time_text:
        return now - timedelta(days=1)
    
    # If we can't parse the relative time, return None
    return None

def format_datetime(date_value):
    """
    Format date to ISO format (YYYY-MM-DDTHH:MM:SS)
    
    Args:
        date_value: Date value to format (string, datetime, or timestamp)
        
    Returns:
        Formatted date string or None if formatting fails
    """
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

def extract_json_data(response, debug=False):
    """
    Extract structured JSON data from the page source
    
    Args:
        response: Scrapy response object
        debug: Whether to log debug information
        
    Returns:
        Dictionary containing extracted JSON data
    """
    # Try to find job data in script tags
    script_data = response.xpath('//script[contains(text(), "jobPostingInfo") or contains(text(), "companyInfo") or contains(text(), "jobData")]/text()').getall()
    
    job_data = {}
    
    for script in script_data:
        # Look for different data patterns
        patterns = [
            r'(\{"data":\{"jobPostingInfo":.*?\})(?=;)',
            r'(\{"data":\{"companyInfo":.*?\})(?=;)',
            r'(\{"data":\{"jobData":.*?\})(?=;)',
            r'(window\.INITIAL_STATE\s*=\s*\{.*?\})(?=;)',
            r'(\{.*?"jobPostingId":.*?\})(?=;)',
            r'(\{.*?"companyId":.*?\})(?=;)'
        ]
        
        for pattern in patterns:
            matches = re.search(pattern, script, re.DOTALL)
            if matches:
                try:
                    import json
                    data = json.loads(matches.group(1))
                    # Merge with existing data
                    job_data.update(data)
                except json.JSONDecodeError:
                    if debug:
                        pass  # Would log warning in real implementation
    
    return job_data