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
        self.output_file = os.path.join(
            os.environ.get('APIFY_LOCAL_STORAGE_DIR', ''), 
            'datasets', 
            'default', 
            'linkedin_jobs_output.json'
        )
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
    
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
        
        # Convert to dictionary for writing to file
        item_dict = dict(adapter)
        
        # Store the item in our collection
        self.items.append(item_dict)
        
        # Push data to Apify dataset using the async event loop
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
        Push item to Apify dataset
        
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
                spider.logger.debug(f"Job data content: {json.dumps(item_dict, ensure_ascii=False, indent=2)}")
        except Exception as e:
            spider.logger.error(f"Error pushing data to Apify dataset: {e}")
            
            # As a fallback, write to a local file
            self._write_to_local_file(item_dict, debug_mode, spider)
    
    def _write_to_local_file(self, item_dict, debug_mode, spider):
        """
        Write item to a local file as a fallback
        
        Args:
            item_dict: Dictionary containing job data
            debug_mode: Boolean flag to control output verbosity
            spider: Spider instance for logging
        """
        try:
            # Generate a unique filename based on job_id or timestamp
            filename = f"{item_dict.get('job_id', datetime.now().timestamp())}.json"
            filepath = os.path.join(
                os.environ.get('APIFY_LOCAL_STORAGE_DIR', ''), 
                'datasets', 
                'default',
                filename
            )
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Print detailed output if in debug mode
            if debug_mode:
                spider.logger.info(f"Writing job data to local file: {filepath}")
            
            # Write the item to a JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(item_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            spider.logger.error(f"Error writing to local file: {e}")
    
    def close_spider(self, spider):
        """
        Called when the spider is closed
        Write all collected items to a single JSON file for easy download
        """
        try:
            # Write all items to a single JSON file
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            
            spider.logger.info(f"Wrote {len(self.items)} jobs to {self.output_file}")
            
            # Also create a CSV file for easy download
            self._write_csv_output(spider)
        except Exception as e:
            spider.logger.error(f"Error writing combined output file: {e}")
    
    def _write_csv_output(self, spider):
        """
        Write the collected items to a CSV file
        """
        try:
            import csv
            
            # Define the CSV file path
            csv_file = os.path.join(
                os.environ.get('APIFY_LOCAL_STORAGE_DIR', ''), 
                'datasets', 
                'default', 
                'linkedin_jobs_output.csv'
            )
            
            # Skip if no items
            if not self.items:
                return
            
            # Get all possible field names from all items
            fieldnames = set()
            for item in self.items:
                fieldnames.update(item.keys())
            
            # Remove HTML description to make CSV more readable
            if 'job_description' in fieldnames:
                fieldnames.remove('job_description')
            
            # Write to CSV
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                writer.writeheader()
                
                for item in self.items:
                    # Create a copy without HTML description for CSV
                    csv_item = {k: v for k, v in item.items() if k != 'job_description'}
                    writer.writerow(csv_item)
            
            spider.logger.info(f"Wrote CSV output to {csv_file}")
        except Exception as e:
            spider.logger.error(f"Error writing CSV output: {e}")