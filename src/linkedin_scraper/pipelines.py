"""
Pipeline for processing LinkedIn job items
"""
import os
import json
import asyncio
from datetime import datetime
from itemadapter import ItemAdapter
from apify import Actor

class LinkedinJobPipeline:
    """
    Pipeline for processing and cleaning LinkedIn job items
    """
    
    def __init__(self):
        """Initialize the pipeline with a list to collect all items"""
        self.items = []
    
    def process_item(self, item, spider):
        """
        Process each scraped job item
        """
        adapter = ItemAdapter(item)
        
        # Clean text fields
        for field in ['job_title', 'company_name', 'location', 'employment_type', 'seniority_level']:
            if adapter.get(field):
                adapter[field] = self._clean_text(adapter[field])
        
        # Clean HTML in job description
        if adapter.get('job_description'):
            adapter['job_description'] = self._clean_html(adapter['job_description'])
        
        # Ensure job_id is present
        if not adapter.get('job_id') and adapter.get('job_url'):
            try:
                adapter['job_id'] = adapter['job_url'].split('?')[0].split('-')[-1]
            except:
                spider.logger.warning(f"Could not extract job_id from URL: {adapter.get('job_url')}")
        
        # Add timestamp if not present
        if not adapter.get('scraped_at'):
            adapter['scraped_at'] = datetime.now().isoformat()
        
        # Convert to dictionary for pushing to Apify dataset
        item_dict = dict(adapter)
        
        # Store the item in our collection for summary
        self.items.append(item_dict)
        
        # Push data to Apify dataset
        self._push_to_apify_dataset(item_dict, spider.debug, spider)
        
        return item
    
    def _clean_text(self, text):
        """
        Clean text by removing extra whitespace
        """
        if not text:
            return ""
        return ' '.join(text.split())
    
    def _clean_html(self, html):
        """
        Basic HTML cleaning - could be expanded with more sophisticated cleaning
        """
        if not html:
            return ""
        return html.strip()
    
    def _push_to_apify_dataset(self, item_dict, debug_mode, spider):
        """
        Push item to Apify dataset using the Actor.push_data method
        
        Args:
            item_dict: Dictionary containing job data
            debug_mode: Boolean flag to control output verbosity
            spider: Spider instance for logging
        """
        try:
            # Use asyncio to run the push_data coroutine
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running event loop, use create_task
                asyncio.create_task(Actor.push_data(item_dict))
            else:
                # Otherwise, run the coroutine directly
                loop.run_until_complete(Actor.push_data(item_dict))
            
            if debug_mode:
                spider.logger.info(f"Pushed job data to Apify dataset: {item_dict.get('job_title')}")
        except Exception as e:
            spider.logger.error(f"Error pushing data to Apify dataset: {e}")
    
    def close_spider(self, spider):
        """
        Called when the spider is closed
        Push a summary of the scraping results
        """
        try:
            # Log completion
            spider.logger.info(f"LinkedIn job scraping completed. Total jobs scraped: {len(self.items)}")
            
            # Push a summary to the dataset
            summary = {
                "type": "summary",
                "jobCount": len(self.items),
                "message": f"Successfully scraped {len(self.items)} LinkedIn jobs",
                "searchParams": {
                    "keyword": getattr(spider, 'keyword', ''),
                    "location": getattr(spider, 'location', ''),
                    "maxJobs": getattr(spider, 'max_jobs', 0),
                    "maxPages": getattr(spider, 'max_pages', 0)
                },
                "completedAt": datetime.now().isoformat()
            }
            
            # Push the summary to Apify dataset
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(Actor.push_data(summary))
            else:
                loop.run_until_complete(Actor.push_data(summary))
                
        except Exception as e:
            spider.logger.error(f"Error pushing summary to Apify dataset: {e}")