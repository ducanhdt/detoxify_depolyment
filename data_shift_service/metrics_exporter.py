"""
Prometheus metrics exporter for Data Shift Detection Service
"""
import logging
from typing import Dict, List, Optional
from prometheus_client import Counter, Gauge, Histogram, Info, CollectorRegistry, generate_latest
from flask import Flask, Response
import threading
import time
from datetime import datetime

from .config import Config
from .shift_detector import LanguageDistribution, ShiftAlert

class MetricsExporter:
    """Handles Prometheus metrics export for data shift monitoring"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.registry = CollectorRegistry()
        self.app = Flask(__name__)
        self._setup_metrics()
        self._setup_routes()
        
    def _setup_metrics(self):
        """Initialize all Prometheus metrics"""
        
        # Language distribution metrics
        self.language_distribution_percentage = Gauge(
            'language_distribution_percentage',
            'Percentage of requests by language for each hour',
            ['language', 'hour'],
            registry=self.registry
        )
        
        self.language_requests_total = Gauge(
            'language_requests_total',
            'Total number of requests by language for each hour',
            ['language', 'hour'],
            registry=self.registry
        )
        
        self.total_requests_hourly = Gauge(
            'total_requests_hourly',
            'Total requests processed in each hour',
            ['hour'],
            registry=self.registry
        )
        
        # Shift detection metrics
        self.language_shift_alerts_total = Counter(
            'language_shift_alerts_total',
            'Total number of shift alerts by language and severity',
            ['language', 'severity', 'shift_type'],
            registry=self.registry
        )
        
        self.language_baseline_deviation = Gauge(
            'language_baseline_deviation',
            'Percentage deviation from baseline for each language',
            ['language'],
            registry=self.registry
        )
        
        self.current_vs_baseline_percentage = Gauge(
            'current_vs_baseline_percentage',
            'Current vs baseline percentage comparison',
            ['language', 'type'],  # type: 'current' or 'baseline'
            registry=self.registry
        )
        
        # Distribution analysis metrics
        self.distribution_entropy = Gauge(
            'distribution_entropy',
            'Shannon entropy of language distribution',
            ['hour'],
            registry=self.registry
        )
        
        self.languages_detected_count = Gauge(
            'languages_detected_count',
            'Number of different languages detected per hour',
            ['hour'],
            registry=self.registry
        )
        
        self.seen_languages_percentage = Gauge(
            'seen_languages_percentage',
            'Percentage of requests from seen languages',
            ['hour'],
            registry=self.registry
        )
        
        self.unseen_languages_percentage = Gauge(
            'unseen_languages_percentage',
            'Percentage of requests from unseen languages',
            ['hour'],
            registry=self.registry
        )
        
        # Service health metrics
        self.service_health = Gauge(
            'data_shift_service_health',
            'Health status of data shift service (1=healthy, 0=unhealthy)',
            registry=self.registry
        )
        
        self.last_analysis_timestamp = Gauge(
            'last_analysis_timestamp',
            'Timestamp of last successful analysis',
            registry=self.registry
        )
        
        self.analysis_duration_seconds = Histogram(
            'analysis_duration_seconds',
            'Duration of analysis operations in seconds',
            ['operation'],
            registry=self.registry
        )
        
        self.analysis_errors_total = Counter(
            'analysis_errors_total',
            'Total number of analysis errors',
            ['error_type'],
            registry=self.registry
        )
        
        # Service info
        self.service_info = Info(
            'data_shift_service_info',
            'Information about the data shift service',
            registry=self.registry
        )
        
        # Set initial service info
        self.service_info.info({
            'version': '1.0.0',
            'supported_languages': ','.join(Config.SUPPORTED_LANGUAGES),
            'detection_threshold_medium': str(Config.DETECTION_THRESHOLD_MEDIUM),
            'detection_threshold_high': str(Config.DETECTION_THRESHOLD_HIGH),
            'baseline_hours': str(Config.BASELINE_HOURS)
        })
        
        self.logger.info("Prometheus metrics initialized")
    
    def _setup_routes(self):
        """Setup Flask routes for metrics endpoint"""
        
        @self.app.route('/metrics')
        def metrics():
            """Prometheus metrics endpoint"""
            return Response(
                generate_latest(self.registry),
                mimetype='text/plain'
            )
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}
    
    def update_language_distribution(self, distributions: List[LanguageDistribution]):
        """Update language distribution metrics"""
        if not distributions:
            return
            
        try:
            hour_str = distributions[0].hour_timestamp.strftime('%Y-%m-%d %H:00:00')
            total_requests = distributions[0].total_requests_hour
            
            # Update total requests for the hour
            self.total_requests_hourly.labels(hour=hour_str).set(total_requests)
            
            # Update per-language metrics
            for dist in distributions:
                language = dist.language_id
                
                self.language_distribution_percentage.labels(
                    language=language,
                    hour=hour_str
                ).set(dist.percentage)
                
                self.language_requests_total.labels(
                    language=language,
                    hour=hour_str
                ).set(dist.request_count)
            
            # Calculate and update summary metrics
            self._update_summary_metrics(distributions, hour_str)
            
            self.logger.debug(f"Updated distribution metrics for hour {hour_str}")
            
        except Exception as e:
            self.logger.error(f"Error updating language distribution metrics: {e}")
            self.analysis_errors_total.labels(error_type='distribution_update').inc()
    
    def update_shift_alerts(self, alerts: List[ShiftAlert]):
        """Update shift alert metrics"""
        if not alerts:
            return
            
        try:
            for alert in alerts:
                # Increment alert counter
                self.language_shift_alerts_total.labels(
                    language=alert.language_id,
                    severity=alert.alert_severity.lower(),
                    shift_type=alert.shift_type
                ).inc()
                
                # Update baseline deviation
                self.language_baseline_deviation.labels(
                    language=alert.language_id
                ).set(alert.percentage_change)
                
                # Update current vs baseline comparison
                self.current_vs_baseline_percentage.labels(
                    language=alert.language_id,
                    type='current'
                ).set(alert.current_percentage)
                
                self.current_vs_baseline_percentage.labels(
                    language=alert.language_id,
                    type='baseline'
                ).set(alert.baseline_percentage)
            
            self.logger.debug(f"Updated shift alert metrics for {len(alerts)} alerts")
            
        except Exception as e:
            self.logger.error(f"Error updating shift alert metrics: {e}")
            self.analysis_errors_total.labels(error_type='alert_update').inc()
    
    def _update_summary_metrics(self, distributions: List[LanguageDistribution], hour_str: str):
        """Update summary metrics from distributions"""
        try:
            # Calculate entropy
            entropy = self._calculate_entropy(distributions)
            self.distribution_entropy.labels(hour=hour_str).set(entropy)
            
            # Count languages detected
            languages_count = len(distributions)
            self.languages_detected_count.labels(hour=hour_str).set(languages_count)
            
            # Calculate seen vs unseen language percentages
            seen_pct = sum(d.percentage for d in distributions 
                          if d.language_id in Config.SEEN_LANGUAGES)
            unseen_pct = sum(d.percentage for d in distributions 
                            if d.language_id in Config.UNSEEN_LANGUAGES)
            
            self.seen_languages_percentage.labels(hour=hour_str).set(seen_pct)
            self.unseen_languages_percentage.labels(hour=hour_str).set(unseen_pct)
            
        except Exception as e:
            self.logger.error(f"Error updating summary metrics: {e}")
    
    def _calculate_entropy(self, distributions: List[LanguageDistribution]) -> float:
        """Calculate Shannon entropy of language distribution"""
        try:
            import math
            
            if not distributions:
                return 0.0
            
            total = sum(d.request_count for d in distributions)
            if total == 0:
                return 0.0
            
            entropy = 0.0
            for dist in distributions:
                if dist.request_count > 0:
                    p = dist.request_count / total
                    entropy -= p * math.log2(p)
            
            return round(entropy, 3)
            
        except Exception:
            return 0.0
    
    def record_analysis_duration(self, operation: str, duration: float):
        """Record analysis operation duration"""
        self.analysis_duration_seconds.labels(operation=operation).observe(duration)
    
    def update_service_health(self, healthy: bool):
        """Update service health status"""
        self.service_health.set(1 if healthy else 0)
    
    def update_last_analysis_timestamp(self, timestamp: datetime):
        """Update last analysis timestamp"""
        self.last_analysis_timestamp.set(timestamp.timestamp())
    
    def record_error(self, error_type: str):
        """Record an error occurrence"""
        self.analysis_errors_total.labels(error_type=error_type).inc()
    
    def run_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the metrics server"""
        def server_thread():
            self.logger.info(f"Starting metrics server on {host}:{port}")
            self.app.run(host=host, port=port, debug=False, use_reloader=False)
        
        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()
        
        # Give the server a moment to start
        time.sleep(1)
        
        self.logger.info(f"Metrics server started on http://{host}:{port}/metrics")
        return thread
    
    def get_current_metrics(self) -> Dict:
        """Get current metrics as dictionary (for debugging)"""
        try:
            metrics_data = {}
            
            # This is a simplified version - in practice you'd parse the registry
            # For now, just return basic info
            metrics_data['service_health'] = self.service_health._value._value
            metrics_data['last_analysis'] = self.last_analysis_timestamp._value._value
            
            return metrics_data
            
        except Exception as e:
            self.logger.error(f"Error getting current metrics: {e}")
            return {}
