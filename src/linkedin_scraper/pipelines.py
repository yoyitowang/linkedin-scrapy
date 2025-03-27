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
        # Create a dataset directory for backup storage
        self.dataset_dir = os.path.join(os.environ.get('APIFY_LOCAL_STORAGE_DIR', ''), 'datasets', 'default')
        os.makedirs(self.dataset_dir, exist_ok=True)
        self.json_output = os.path.join(self.dataset_dir, 'linkedin_jobs_output.json')
        self.csv_output = os.path.join(self.dataset_dir, 'linkedin_jobs_output.csv')
    
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
        
        # Store the item in our collection for summary and backup
        self.items.append(item_dict)
        
        # Write to local JSON file as a backup
        self._write_json_backup()
        
        # Log pushed data
        if spider.debug:
            spider.logger.info(f"Processed job data: {item_dict.get('job_title')}")
        
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
            print(f"Error writing JSON backup: {e}")
    
    def _write_csv_backup(self):
        """Write all collected items to a CSV file as backup"""
        try:
            import csv
            
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
            with open(self.csv_output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                writer.writeheader()
                
                for item in self.items:
                    # Create a copy without HTML description for CSV
                    csv_item = {k: v for k, v in item.items() if k != 'job_description'}
                    writer.writerow(csv_item)
        except Exception as e:
            print(f"Error writing CSV backup: {e}")
    
    def close_spider(self, spider):
        """
        Called when the spider is closed
        Push all collected data to Apify dataset at once
        """
        try:
            # Write CSV backup
            self._write_csv_backup()
            
            # Log completion
            spider.logger.info(f"LinkedIn job scraping completed. Total jobs scraped: {len(self.items)}")
            
            # Add a summary item
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
            
            # Add summary to items list
            self.items.append(summary)
            
            # Update the JSON backup with summary
            self._write_json_backup()
            
            # Push all data to Apify dataset at once (after spider is closed)
            # This will be handled by the main.py file
                
        except Exception as e:
            spider.logger.error(f"Error in close_spider: {e}")