"""
Log processor for fetching and cleaning Google Cloud Logging data
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from google.cloud import logging as cloud_logging
from google.cloud.logging_v2 import Client as LoggingClient
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client
from google.api_core.exceptions import GoogleCloudError
import time

from .config import Config

@dataclass
class InferenceLog:
    """Data class for inference log entries"""
    timestamp: datetime
    request_id: str
    language_id: str
    input_text_length: int
    model_used: str
    actual_model_id: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    toxicity_terms_detected: List[str]

class LogProcessor:
    """Handles log fetching and processing from Google Cloud Logging"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.project_id = Config.GCP_PROJECT_ID
        self.log_name = Config.LOG_NAME
        self._init_client()
    
    def _init_client(self):
        """Initialize Google Cloud Logging client"""
        try:
            self.client = cloud_logging.Client(project=self.project_id)
            self.logger.info(f"Initialized Cloud Logging client for project: {self.project_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Cloud Logging client: {e}")
            raise
    
    def fetch_logs(self, start_time: datetime, end_time: datetime) -> List[InferenceLog]:
        """
        Fetch inference logs from Cloud Logging for the specified time range
        
        Args:
            start_time: Start time for log fetch
            end_time: End time for log fetch
            
        Returns:
            List of InferenceLog objects
        """
        self.logger.info(f"Fetching logs from {start_time} to {end_time}")
        
        try:
            # Build the filter query
            filter_query = self._build_filter_query(start_time, end_time)
            
            # Fetch logs
            entries = self.client.list_entries(
                filter_=filter_query,
                page_size=Config.BATCH_SIZE,
                order_by=cloud_logging.DESCENDING
            )
            
            # Process entries
            logs = []
            processed_count = 0
            
            for entry in entries:
                try:
                    log_entry = self._parse_log_entry(entry)
                    if log_entry:
                        logs.append(log_entry)
                        processed_count += 1
                        
                        if processed_count % 100 == 0:
                            self.logger.debug(f"Processed {processed_count} log entries")
                            
                except Exception as e:
                    self.logger.warning(f"Failed to parse log entry: {e}")
                    continue
            
            self.logger.info(f"Successfully fetched {len(logs)} inference logs")
            return logs
            
        except GoogleCloudError as e:
            self.logger.error(f"Google Cloud error while fetching logs: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching logs: {e}")
            raise
    
    def _build_filter_query(self, start_time: datetime, end_time: datetime) -> str:
        """Build Cloud Logging filter query"""
        base_filter = Config.get_log_filter()
        
        # Add time range filter
        time_filter = f"""
        timestamp >= "{start_time.isoformat()}Z" AND
        timestamp <= "{end_time.isoformat()}Z"
        """
        
        return f"{base_filter} AND {time_filter}"
    
    def _parse_log_entry(self, entry) -> Optional[InferenceLog]:
        """Parse a single log entry into InferenceLog object"""
        try:
            # Check if entry has required fields
            if not hasattr(entry, 'payload') or not hasattr(entry.payload, 'json_payload'):
                return None
            
            payload = entry.payload.json_payload
            
            # Extract required fields
            request_id = payload.get('request_id')
            language_id = payload.get('language_id')
            
            if not request_id or not language_id:
                return None
            
            # Parse timestamp
            timestamp = entry.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            # Extract other fields with defaults
            input_text_length = payload.get('input_text_length', 0)
            model_used = payload.get('model_used', 'unknown')
            actual_model_id = payload.get('actual_model_id', 'unknown')
            latency_ms = float(payload.get('latency_ms', 0))
            prompt_tokens = int(payload.get('prompt_tokens', 0))
            completion_tokens = int(payload.get('completion_tokens', 0))
            total_tokens = int(payload.get('total_tokens', 0))
            
            # Parse toxicity terms
            toxicity_terms = payload.get('toxicity_terms_detected', [])
            if isinstance(toxicity_terms, str):
                try:
                    toxicity_terms = json.loads(toxicity_terms)
                except json.JSONDecodeError:
                    toxicity_terms = [toxicity_terms] if toxicity_terms else []
            
            return InferenceLog(
                timestamp=timestamp,
                request_id=request_id,
                language_id=language_id,
                input_text_length=input_text_length,
                model_used=model_used,
                actual_model_id=actual_model_id,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                toxicity_terms_detected=toxicity_terms
            )
            
        except Exception as e:
            self.logger.warning(f"Error parsing log entry: {e}")
            return None
    
    def delete_old_logs(self, cutoff_time: datetime) -> bool:
        """
        Delete logs older than cutoff_time to save costs
        
        Args:
            cutoff_time: Delete logs older than this time
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Deleting logs older than {cutoff_time}")
        
        try:
            # Build deletion filter
            deletion_filter = f"""
            {Config.get_log_filter()} AND
            timestamp < "{cutoff_time.isoformat()}Z"
            """
            
            # List entries to delete
            entries_to_delete = list(self.client.list_entries(
                filter_=deletion_filter,
                page_size=1000  # Delete in batches
            ))
            
            if not entries_to_delete:
                self.logger.info("No old logs found to delete")
                return True
            
            # Delete entries
            deleted_count = 0
            for entry in entries_to_delete:
                try:
                    entry.delete()
                    deleted_count += 1
                    
                    if deleted_count % 100 == 0:
                        self.logger.debug(f"Deleted {deleted_count} log entries")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to delete log entry: {e}")
                    continue
            
            self.logger.info(f"Successfully deleted {deleted_count} old log entries")
            return True
            
        except GoogleCloudError as e:
            self.logger.error(f"Google Cloud error while deleting logs: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error while deleting logs: {e}")
            return False
    
    def get_log_statistics(self, start_time: datetime, end_time: datetime) -> Dict:
        """
        Get statistics about logs in the specified time range
        
        Args:
            start_time: Start time for analysis
            end_time: End time for analysis
            
        Returns:
            Dictionary with log statistics
        """
        try:
            logs = self.fetch_logs(start_time, end_time)
            
            # Calculate statistics
            total_logs = len(logs)
            
            # Language distribution
            language_counts = {}
            for log in logs:
                language_counts[log.language_id] = language_counts.get(log.language_id, 0) + 1
            
            # Model usage
            model_counts = {}
            for log in logs:
                model_counts[log.model_used] = model_counts.get(log.model_used, 0) + 1
            
            # Average metrics
            avg_latency = sum(log.latency_ms for log in logs) / total_logs if total_logs > 0 else 0
            avg_tokens = sum(log.total_tokens for log in logs) / total_logs if total_logs > 0 else 0
            
            # Toxicity detection
            toxicity_detections = sum(1 for log in logs if log.toxicity_terms_detected)
            
            return {
                'total_logs': total_logs,
                'language_distribution': language_counts,
                'model_usage': model_counts,
                'avg_latency_ms': avg_latency,
                'avg_tokens': avg_tokens,
                'toxicity_detections': toxicity_detections,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating log statistics: {e}")
            return {}
    
    def health_check(self) -> bool:
        """
        Check if the log processor is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to fetch recent logs to verify connectivity
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            
            filter_query = self._build_filter_query(start_time, end_time)
            
            # Just check if we can list entries (limit to 1)
            entries = list(self.client.list_entries(
                filter_=filter_query,
                page_size=1
            ))
            
            self.logger.info("Log processor health check passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Log processor health check failed: {e}")
            return False
