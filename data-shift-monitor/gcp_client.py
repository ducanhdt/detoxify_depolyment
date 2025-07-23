import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.cloud import logging as gcp_logging
from google.oauth2 import service_account

# logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GCPLogClient")

class GCPLogClient:
    def __init__(self, project_id: str, log_name: str = "llm-detox-inference-logs"):
        """
        Initialize GCP Log Client
        
        Args:
            project_id: GCP project ID
            log_name: Name of the log to query
        """
        self.project_id = project_id
        self.log_name = log_name
        
        # Initialize client with credentials
        self.client = self._create_client()
        
    def _create_client(self) -> gcp_logging.Client:
        """
        Create GCP logging client with proper credentials
        
        Returns:
            Initialized GCP logging client
        """
        credentials_path = "/app/credentials.json"
        if os.path.exists(credentials_path):
            logger.info(f"Loading GCP credentials from {credentials_path}")
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
            )
            return gcp_logging.Client(project=self.project_id, credentials=credentials)
        
        # Fallback to default credentials (for local development)
        logger.info("Using default GCP credentials")
        return gcp_logging.Client(project=self.project_id)
        
    def query_logs(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Query logs from GCP Cloud Logging
        
        Args:
            start_time: Start time for log query
            end_time: End time for log query
            
        Returns:
            List of log entries with extracted data
        """
        
        try:
            # Format timestamps for GCP logging query
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            # Build the filter query
            filter_query = f'''
                logName="projects/{self.project_id}/logs/{self.log_name}"
                AND timestamp >= "{start_time_str}"
                AND timestamp <= "{end_time_str}"
                AND jsonPayload.input_text != ""
            '''
            
            logger.info(f"Querying logs from {start_time_str} to {end_time_str}")
            
            # Execute the query
            entries = self.client.list_entries(filter_=filter_query)
            
            log_data = []
            for entry in entries:
                if hasattr(entry, 'payload') and entry.payload:
                    payload = entry.payload

                    # Extract text and language information
                    text = payload.get('input_text', '')
                    language_id = payload.get('language_id', '')

                    if text and language_id:
                        log_data.append({
                            **payload,
                            'text_length': len(text),
                            'timestamp': entry.timestamp,
                            # 'text': text,
                            # 'language_id': language_id,
                            # 'request_id': payload.get('request_id', ''),
                            # 'model_used': payload.get('model_used', '')
                        })
            
            logger.info(f"Retrieved {len(log_data)} log entries")
            return log_data
            
        except Exception as e:
            logger.error(f"Error querying logs: {e}")
            raise
    
    def get_recent_logs(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get logs from the last N minutes
        
        Args:
            minutes: Number of minutes to look back
            
        Returns:
            List of recent log entries
        """
        #get current time and calculate start time
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)
        
        return self.query_logs(start_time, end_time)
    
    def test_connection(self) -> bool:
        """
        Test connection to GCP logging
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to query the last 5 minutes of logs
            test_logs = self.get_recent_logs(minutes=5)
            logger.info(f"Connection test successful. Found {len(test_logs)} recent entries")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
if __name__ == "__main__":
    log_client = GCPLogClient(project_id="meta-triode-457409-a9")
    data = log_client.get_recent_logs(minutes=10)
    print(data)
    
    