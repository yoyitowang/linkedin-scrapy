"""
Pipeline for processing LinkedIn job items
"""
import os
import json
import logging
from datetime import datetime
from itemadapter import ItemAdapter

class LinkedinJobPipeline:
    """
    Pipeline for processing and cleaning LinkedIn job items
    """
    
    def __init__(self):
        """Initialize the pipeline with a list to collect all items"""
        self.items = []
        # Create a dataset directory for local storage
        self.local_storage_dir = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
        self.dataset_dir = os.path.join(self.local_storage_dir, 'datasets', 'default')
        os.makedirs(self.dataset_dir, exist_ok=True)
        self.json_output = os.path.join(self.dataset_dir, 'linkedin_jobs_output.json')
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Pipeline initialized. Output will be saved to: {self.json_output}")
    
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
            except Exception as e:
                spider.logger.warning(f"Could not extract job_id from URL: {adapter.get('job_url')} - {e}")
        
        # Add timestamp if not present
        if not adapter.get('scraped_at'):
            adapter['scraped_at'] = datetime.now().isoformat()
        
        # Convert to dictionary for storing
        item_dict = dict(adapter)
        
        # Store the item in our collection
        self.items.append(item_dict)
        
        # Write to local JSON file after each item (for safety)
        self._write_json_backup()
        
        # Log minimal info
        if spider.debug:
            spider.logger.info(f"Processed job: {item_dict.get('job_title')} - Total: {len(self.items)}")
        
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
    
    def _write_json_backup(self):
        """Write all collected items to a JSON file as backup"""
        try:
            with open(self.json_output, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Error writing JSON backup: {e}")
            # Try with absolute path
            try:
                abs_path = os.path.abspath(self.json_output)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    json.dump(self.items, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Successfully wrote to absolute path: {abs_path}")
            except Exception as e2:
                self.logger.error(f"Error writing to absolute path: {e2}")
    
    def close_spider(self, spider):
        """
        Called when the spider is closed
        Finalize data collection
        """
        try:
            # Write final JSON backup
            self._write_json_backup()
            
            # Log completion
            spider.logger.info(f"LinkedIn job scraping completed. Total jobs scraped: {len(self.items)}")
            spider.logger.info(f"Data saved to: {os.path.abspath(self.json_output)}")
            
            # Print directory contents for debugging
            try:
                if spider.debug:
                    spider.logger.info(f"Contents of dataset directory: {os.listdir(self.dataset_dir)}")
            except Exception as e:
                spider.logger.error(f"Error listing directory contents: {e}")
                
        except Exception as e:
            spider.logger.error(f"Error in close_spider: {e}")