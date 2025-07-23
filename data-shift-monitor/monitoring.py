import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from gcp_client import GCPLogClient
from metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)

class DataShiftMonitor:
    def __init__(self, baseline_file: str = "baseline.json"):
        """
        Initialize Data Shift Monitor
        
        Args:
            baseline_file: Path to baseline configuration file
        """
        self.baseline_file = baseline_file
        self.gcp_project_id = os.getenv("GCP_PROJECT_ID", "meta-triode-457409-a9")
        self.log_name = "llm-detox-inference-logs"
        
        # Initialize components
        self.gcp_client = GCPLogClient(self.gcp_project_id, self.log_name)
        self.metrics_calculator = MetricsCalculator()
        
        # Load baseline data
        self.baseline_data = self._load_baseline()
        
        logger.info(f"DataShiftMonitor initialized with project: {self.gcp_project_id}")
    
    def _load_baseline(self) -> Dict[str, Any]:
        """
        Load baseline data from file
        
        Returns:
            Baseline data dictionary
        """
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r') as f:
                    baseline = json.load(f)
                    logger.info(f"Loaded baseline data from {self.baseline_file}")
                    return baseline
            else:
                # Create default baseline if file doesn't exist
                default_baseline = {
                    "avg_text_length": 100.0,
                    "text_length_std": 50.0,
                    "language_distribution": {
                        "en": 80.0,
                        "es": 10.0,
                        "fr": 5.0,
                        "de": 3.0,
                        "it": 2.0
                    },
                    "avg_request_volume": 10.0,
                    "created_at": datetime.now().isoformat(),
                    "description": "Default baseline - please update with actual data"
                }
                
                self._save_baseline(default_baseline)
                logger.warning(f"Created default baseline at {self.baseline_file}")
                return default_baseline
                
        except Exception as e:
            logger.error(f"Error loading baseline: {e}")
            raise
    
    def _save_baseline(self, baseline_data: Dict[str, Any]) -> None:
        """
        Save baseline data to file
        
        Args:
            baseline_data: Baseline data to save
        """
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(baseline_data, f, indent=2)
            logger.info(f"Baseline data saved to {self.baseline_file}")
        except Exception as e:
            logger.error(f"Error saving baseline: {e}")
            raise
    
    async def check_data_shift(self, lookback_minutes: int = 60) -> Dict[str, Any]:
        """
        Check for data shift by comparing recent data to baseline
        
        Args:
            lookback_minutes: Number of minutes to look back for current data
            
        Returns:
            Dictionary with shift analysis results
        """
        try:
            logger.info(f"Starting data shift check with {lookback_minutes} minute lookback")
            
            # Get recent log data
            recent_logs = self.gcp_client.get_recent_logs(minutes=lookback_minutes)
            
            if not recent_logs:
                logger.warning("No recent logs found")
                return {
                    "status": "no_data",
                    "message": "No recent logs found for analysis",
                    "timestamp": datetime.now().isoformat(),
                    "text_length_change": 0.0,
                    "language_distribution_change": 0.0,
                    "request_volume_change": 0.0,
                    "total_requests": 0
                }
            
            # Calculate current metrics
            current_metrics = self.metrics_calculator.process_log_data(recent_logs)
            logger.info(f"Current metrics calculated: {current_metrics}")
            logger.info("Calculating data shift metrics")
            # Calculate data shift
            shift_metrics = self.metrics_calculator.calculate_data_shift(
                current_metrics, self.baseline_data
            )
            
            # Prepare result
            result = {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "lookback_minutes": lookback_minutes,
                "total_requests": len(recent_logs),
                "current_metrics": current_metrics,
                "baseline_metrics": self.baseline_data,
                **shift_metrics
            }
            
            # Log significant changes
            self._log_significant_changes(shift_metrics)
            
            logger.info("Data shift check completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in data shift check: {e}")
            # log traceback for debugging
            import traceback
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "text_length_change": 0.0,
                "language_distribution_change": 0.0,
                "request_volume_change": 0.0,
                "total_requests": 0
            }
    
    def _log_significant_changes(self, shift_metrics: Dict[str, float], threshold: float = 20.0) -> None:
        """
        Log significant changes in metrics
        
        Args:
            shift_metrics: Calculated shift metrics
            threshold: Percentage threshold for significant changes
        """
        for metric_name, value in shift_metrics.items():
            if abs(value) > threshold:
                logger.warning(f"Significant change detected in {metric_name}: {value:.2f}%")
    
    def get_baseline(self) -> Dict[str, Any]:
        """
        Get current baseline data
        
        Returns:
            Current baseline data
        """
        return self.baseline_data
    
    def update_baseline(self, new_baseline: Dict[str, Any]) -> None:
        """
        Update baseline data
        
        Args:
            new_baseline: New baseline data
        """
        self.baseline_data = new_baseline
        self._save_baseline(new_baseline)
        logger.info("Baseline data updated successfully")
    
    def test_connection(self) -> bool:
        """
        Test connection to GCP logging
        
        Returns:
            True if connection successful
        """
        return self.gcp_client.test_connection()
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the monitoring system
        
        Returns:
            Health status information
        """
        try:
            # Test GCP connection
            gcp_healthy = self.test_connection()
            
            # Check if baseline is loaded
            baseline_healthy = bool(self.baseline_data)
            
            overall_healthy = gcp_healthy and baseline_healthy
            
            return {
                "overall_healthy": overall_healthy,
                "gcp_connection": gcp_healthy,
                "baseline_loaded": baseline_healthy,
                "project_id": self.gcp_project_id,
                "log_name": self.log_name,
                "baseline_file": self.baseline_file,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                "overall_healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
