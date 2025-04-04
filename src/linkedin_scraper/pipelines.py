"""
Pipeline for processing LinkedIn job items
"""
import os
import json
import logging
import traceback
from datetime import datetime
from itemadapter import ItemAdapter

class LinkedinJobPipeline:
    """
    Pipeline for processing and cleaning LinkedIn job items
    """
    
    def __init__(self):
        """Initialize the pipeline with a list to collect all items"""
        self.items = []
        
        # Create a dataset directory for local storage - try multiple paths
        self.local_storage_dir = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
        self.dataset_dir = os.path.join(self.local_storage_dir, 'datasets', 'default')
        os.makedirs(self.dataset_dir, exist_ok=True)
        
        # Define multiple possible output paths
        self.json_output = os.path.join(self.dataset_dir, 'linkedin_jobs_output.json')
        self.alt_output_1 = '/usr/src/app/apify_storage/datasets/default/linkedin_jobs_output.json'
        self.alt_output_2 = '/tmp/linkedin_jobs_output.json'
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Log all paths we'll try to use
        self.logger.info(f"Pipeline initialized. Primary output path: {self.json_output}")
        self.logger.info(f"Alternative output path 1: {self.alt_output_1}")
        self.logger.info(f"Alternative output path 2: {self.alt_output_2}")
        
        # Add a test item to verify pipeline is working
        self.test_item = {
            "job_id": "test_job_id",
            "job_title": "Test Job Title",
            "company_name": "Test Company",
            "location": "Test Location",
            "job_url": "https://www.linkedin.com/jobs/view/test-job-id",
            "scraped_at": datetime.now().isoformat(),
            "is_test_item": True
        }
        self.items.append(self.test_item)
        self.logger.info("Added test item to verify pipeline functionality")
        
        # Write initial file to all possible locations
        self._write_json_backup()
        
        # Verify the files were created
        self._verify_files_exist()
    
    def _verify_files_exist(self):
        """Verify that output files exist and have content"""
        paths_to_check = [self.json_output, self.alt_output_1, self.alt_output_2]
        
        for path in paths_to_check:
            try:
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    self.logger.info(f"✅ File exists at {path} with size {size} bytes")
                else:
                    self.logger.warning(f"❌ File does not exist at {path}")
            except Exception as e:
                self.logger.error(f"Error checking file at {path}: {e}")
    
    def process_item(self, item, spider):
        """
        Process each scraped job item
        """
        try:
            spider.logger.info(f"Pipeline received job item: {item.get('job_title', 'Unknown title')}")
            
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
            
            # Log the current count
            spider.logger.info(f"Added job to collection. Current total: {len(self.items)} jobs")
            
            # Write to local JSON file after each item (for safety)
            self._write_json_backup()
            
            spider.logger.info(f"=======================================")
            return item
        except Exception as e:
            spider.logger.error(f"Error processing item: {e}")
            spider.logger.error(traceback.format_exc())
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
        # Try multiple file paths to ensure data is saved somewhere
        paths_to_try = [
            self.json_output,
            self.alt_output_1,
            self.alt_output_2,
            # Add absolute paths
            os.path.abspath(self.json_output),
            # Try different directory structures
            '/apify_storage/datasets/default/linkedin_jobs_output.json',
            './apify_storage/datasets/default/linkedin_jobs_output.json'
        ]
        
        success = False
        for path in paths_to_try:
            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                # Write the file
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.items, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Successfully wrote {len(self.items)} items to: {path}")
                success = True
            except Exception as e:
                self.logger.warning(f"Error writing to {path}: {e}")
        
        if not success:
            self.logger.error("Failed to write to any output path!")
            self.logger.error(f"Current directory: {os.getcwd()}")
            try:
                self.logger.error(f"Directory contents: {os.listdir('.')}")
                self.logger.error(f"Parent directory contents: {os.listdir('..')}")
                self.logger.error(f"Dataset directory exists: {os.path.exists(self.dataset_dir)}")
                if os.path.exists(self.dataset_dir):
                    self.logger.error(f"Dataset directory contents: {os.listdir(self.dataset_dir)}")
            except Exception as e:
                self.logger.error(f"Error listing directories: {e}")
    
    def close_spider(self, spider):
        """
        Called when the spider is closed
        Finalize data collection
        """
        try:
            # Log item count
            spider.logger.info(f"Spider closing. Total items collected: {len(self.items)}")
            
            # If we only have the test item, add a dummy job to ensure we have real output
            if len(self.items) <= 1:
                spider.logger.warning("No real jobs found. Adding a dummy job for demonstration.")
                dummy_job = {
                    "job_id": "dummy_job_id",
                    "job_title": "Dummy Job Title - No real jobs were scraped",
                    "company_name": "Dummy Company",
                    "location": "Dummy Location",
                    "job_url": "https://www.linkedin.com/jobs/view/dummy-job-id",
                    "job_description": "<p>This is a dummy job created because no real jobs were scraped. This could be due to LinkedIn's anti-scraping measures or incorrect search parameters.</p>",
                    "scraped_at": datetime.now().isoformat(),
                    "is_dummy_item": True,
                    "note": "No real jobs were found during scraping. Check your search parameters and LinkedIn access."
                }
                self.items.append(dummy_job)
            
            # Write final JSON backup
            self._write_json_backup()
            
            # Log completion
            spider.logger.info(f"LinkedIn job scraping completed. Total jobs scraped: {len(self.items)}")
            
            # Print directory contents for debugging
            try:
                if os.path.exists(self.dataset_dir):
                    spider.logger.info(f"Contents of dataset directory: {os.listdir(self.dataset_dir)}")
                
                # Check each possible output file
                for path in [self.json_output, self.alt_output_1, self.alt_output_2]:
                    if os.path.exists(path):
                        file_size = os.path.getsize(path)
                        spider.logger.info(f"Output file {path} exists with size: {file_size} bytes")
                    else:
                        spider.logger.warning(f"Output file {path} does not exist")
            except Exception as e:
                spider.logger.error(f"Error checking output file: {e}")
                spider.logger.error(traceback.format_exc())
                
        except Exception as e:
            spider.logger.error(f"Error in close_spider: {e}")
            spider.logger.error(traceback.format_exc())