"""
Grafana integration for pushing metrics and annotations
"""
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import asdict

from .config import Config
from .shift_detector import LanguageDistribution, ShiftAlert

class GrafanaPusher:
    """Handles pushing metrics and annotations to Grafana"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = Config.GRAFANA_URL.rstrip('/')
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self):
        """Setup authentication for Grafana API"""
        if Config.GRAFANA_API_KEY:
            self.session.headers.update({
                'Authorization': f'Bearer {Config.GRAFANA_API_KEY}',
                'Content-Type': 'application/json'
            })
        else:
            self.session.auth = (Config.GRAFANA_USERNAME, Config.GRAFANA_PASSWORD)
            self.session.headers.update({'Content-Type': 'application/json'})
    
    def push_language_distribution(self, distributions: List[LanguageDistribution]) -> bool:
        """
        Push language distribution metrics to Grafana
        
        Args:
            distributions: List of language distributions to push
            
        Returns:
            True if successful, False otherwise
        """
        if not distributions:
            self.logger.warning("No distributions to push")
            return True
        
        try:
            # Create metrics payload
            metrics = self._create_distribution_metrics(distributions)
            
            # Push metrics via Grafana's metrics API (if available)
            # For now, we'll store in annotations as a fallback
            return self._push_as_annotations(metrics, "language_distribution")
            
        except Exception as e:
            self.logger.error(f"Error pushing language distribution: {e}")
            return False
    
    def push_shift_alerts(self, alerts: List[ShiftAlert]) -> bool:
        """
        Push shift alerts as annotations to Grafana
        
        Args:
            alerts: List of shift alerts to push
            
        Returns:
            True if successful, False otherwise
        """
        if not alerts:
            self.logger.info("No alerts to push")
            return True
        
        try:
            success_count = 0
            
            for alert in alerts:
                annotation_data = self._create_alert_annotation(alert)
                
                if self._push_annotation(annotation_data):
                    success_count += 1
                else:
                    self.logger.warning(f"Failed to push alert for {alert.language_id}")
            
            self.logger.info(f"Successfully pushed {success_count}/{len(alerts)} alerts")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error pushing shift alerts: {e}")
            return False
    
    def _create_distribution_metrics(self, distributions: List[LanguageDistribution]) -> Dict:
        """Create metrics payload for language distributions"""
        if not distributions:
            return {}
        
        # Group by hour
        hour_timestamp = distributions[0].hour_timestamp
        total_requests = distributions[0].total_requests_hour
        
        metrics = {
            'timestamp': int(hour_timestamp.timestamp() * 1000),
            'hour': hour_timestamp.isoformat(),
            'total_requests': total_requests,
            'languages': {}
        }
        
        for dist in distributions:
            metrics['languages'][dist.language_id] = {
                'count': dist.request_count,
                'percentage': dist.percentage
            }
        
        return metrics
    
    def _create_alert_annotation(self, alert: ShiftAlert) -> Dict:
        """Create annotation payload for shift alert"""
        # Determine annotation color based on severity
        color_map = {
            'HIGH': 'red',
            'MEDIUM': 'orange',
            'LOW': 'yellow'
        }
        
        # Create annotation text
        if alert.shift_type == 'new_language':
            text = f"NEW LANGUAGE: {alert.language_id} ({alert.current_percentage:.1f}%)"
        elif alert.shift_type == 'disappeared':
            text = f"LANGUAGE DISAPPEARED: {alert.language_id} (was {alert.baseline_percentage:.1f}%)"
        else:
            direction = "↑" if alert.percentage_change > 0 else "↓"
            text = f"{alert.language_id}: {direction} {abs(alert.percentage_change):.1f}% change ({alert.baseline_percentage:.1f}% → {alert.current_percentage:.1f}%)"
        
        return {
            'time': int(alert.analysis_hour.timestamp() * 1000),
            'timeEnd': int((alert.analysis_hour + timedelta(hours=1)).timestamp() * 1000),
            'tags': [
                'language_shift',
                alert.alert_severity.lower(),
                alert.shift_type,
                alert.language_id
            ],
            'text': text,
            'title': f"Language Shift Alert - {alert.alert_severity}",
            'color': color_map.get(alert.alert_severity, 'blue')
        }
    
    def _push_annotation(self, annotation_data: Dict) -> bool:
        """Push a single annotation to Grafana"""
        try:
            url = f"{self.base_url}/api/annotations"
            
            response = self.session.post(url, json=annotation_data)
            
            if response.status_code in [200, 201]:
                self.logger.debug(f"Successfully pushed annotation: {annotation_data['title']}")
                return True
            else:
                self.logger.warning(f"Failed to push annotation: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error pushing annotation: {e}")
            return False
    
    def _push_as_annotations(self, metrics: Dict, annotation_type: str) -> bool:
        """Push metrics as annotations (fallback method)"""
        try:
            annotation_data = {
                'time': metrics.get('timestamp', int(datetime.now().timestamp() * 1000)),
                'tags': [annotation_type, 'metrics'],
                'text': json.dumps(metrics, indent=2),
                'title': f"Language Distribution - {metrics.get('hour', 'Unknown')}",
                'color': 'blue'
            }
            
            return self._push_annotation(annotation_data)
            
        except Exception as e:
            self.logger.error(f"Error pushing metrics as annotations: {e}")
            return False
    
    def create_dashboard_alert(self, alert: ShiftAlert) -> bool:
        """
        Create a dashboard alert rule (if supported)
        
        Args:
            alert: The shift alert to create dashboard alert for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This would create actual alert rules in Grafana
            # For now, we'll just push as annotation
            return self._push_annotation(self._create_alert_annotation(alert))
            
        except Exception as e:
            self.logger.error(f"Error creating dashboard alert: {e}")
            return False
    
    def update_dashboard_variables(self, variables: Dict) -> bool:
        """
        Update dashboard variables
        
        Args:
            variables: Dictionary of variables to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This would update dashboard variables
            # Implementation depends on specific dashboard setup
            self.logger.info(f"Dashboard variables update requested: {variables}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating dashboard variables: {e}")
            return False
    
    def push_health_status(self, status: Dict) -> bool:
        """
        Push service health status to Grafana
        
        Args:
            status: Health status dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            annotation_data = {
                'time': int(datetime.now().timestamp() * 1000),
                'tags': ['health_check', 'service_status'],
                'text': json.dumps(status, indent=2),
                'title': f"Data Shift Service Health - {status.get('status', 'unknown')}",
                'color': 'green' if status.get('status') == 'healthy' else 'red'
            }
            
            return self._push_annotation(annotation_data)
            
        except Exception as e:
            self.logger.error(f"Error pushing health status: {e}")
            return False
    
    def get_dashboard_info(self) -> Optional[Dict]:
        """
        Get information about the monitoring dashboard
        
        Returns:
            Dashboard info if available, None otherwise
        """
        try:
            # Search for the language distribution dashboard
            url = f"{self.base_url}/api/search"
            params = {'query': 'Language Distribution Monitoring'}
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                dashboards = response.json()
                if dashboards:
                    return dashboards[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard info: {e}")
            return None
    
    def health_check(self) -> bool:
        """
        Check if Grafana is accessible
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/health"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("Grafana health check passed")
                return True
            else:
                self.logger.warning(f"Grafana health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Grafana health check error: {e}")
            return False
    
    def clear_old_annotations(self, days: int = 7) -> bool:
        """
        Clear old annotations to prevent clutter
        
        Args:
            days: Number of days to keep annotations
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_timestamp = int(cutoff_time.timestamp() * 1000)
            
            # Get annotations older than cutoff
            url = f"{self.base_url}/api/annotations"
            params = {
                'to': cutoff_timestamp,
                'tags': ['language_shift', 'language_distribution']
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                old_annotations = response.json()
                
                deleted_count = 0
                for annotation in old_annotations:
                    delete_url = f"{self.base_url}/api/annotations/{annotation['id']}"
                    delete_response = self.session.delete(delete_url)
                    
                    if delete_response.status_code == 200:
                        deleted_count += 1
                
                self.logger.info(f"Deleted {deleted_count} old annotations")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error clearing old annotations: {e}")
            return False
