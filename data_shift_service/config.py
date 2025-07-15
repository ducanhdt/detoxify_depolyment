"""
Configuration management for Data Shift Detection Service
"""
import os
from datetime import timedelta
from typing import Dict, List, Optional

class Config:
    """Configuration class for the data shift detection service"""
    
    # Google Cloud Configuration
    GCP_PROJECT_ID: str = os.getenv('GCP_PROJECT_ID', 'meta-triode-457409-a9')
    CREDENTIALS_PATH: str = os.getenv('CREDENTIALS_PATH', '/app/credentials.json')
    
    # Logging Configuration
    LOG_NAME: str = 'llm-detox-inference-logs'
    LOG_RETENTION_HOURS: int = int(os.getenv('LOG_RETENTION_HOURS', '48'))  # Keep logs for 48 hours
    
    # BigQuery Configuration
    BIGQUERY_DATASET: str = 'llm_monitoring'
    BIGQUERY_TABLE_DISTRIBUTION: str = 'hourly_language_distribution'
    BIGQUERY_TABLE_ALERTS: str = 'language_distribution_alerts'
    USE_BIGQUERY_STORAGE: bool = os.getenv('USE_BIGQUERY_STORAGE', 'true').lower() == 'true'
    
    # Grafana Configuration
    GRAFANA_URL: str = os.getenv('GRAFANA_URL', 'http://grafana:3000')
    GRAFANA_USERNAME: str = os.getenv('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD: str = os.getenv('GRAFANA_PASSWORD', 'admin')
    GRAFANA_API_KEY: Optional[str] = os.getenv('GRAFANA_API_KEY')  # Optional: use API key instead
    
    # Detection Configuration
    DETECTION_THRESHOLD_MEDIUM: float = float(os.getenv('DETECTION_THRESHOLD_MEDIUM', '20.0'))  # 20% change
    DETECTION_THRESHOLD_HIGH: float = float(os.getenv('DETECTION_THRESHOLD_HIGH', '50.0'))    # 50% change
    BASELINE_HOURS: int = int(os.getenv('BASELINE_HOURS', '24'))  # 24 hours baseline
    MIN_BASELINE_HOURS: int = int(os.getenv('MIN_BASELINE_HOURS', '12'))  # Minimum 12 hours for baseline
    
    # Scheduling Configuration
    SCHEDULE_HOUR: int = int(os.getenv('SCHEDULE_HOUR', '0'))  # Run at minute 0 of every hour
    SCHEDULE_MINUTE: int = int(os.getenv('SCHEDULE_MINUTE', '5'))  # Run at minute 5 of every hour
    
    # Alert Configuration
    ENABLE_EMAIL_ALERTS: bool = os.getenv('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
    ENABLE_SLACK_ALERTS: bool = os.getenv('ENABLE_SLACK_ALERTS', 'false').lower() == 'true'
    
    # Email Configuration
    SMTP_SERVER: str = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', '587'))
    EMAIL_USER: str = os.getenv('EMAIL_USER', '')
    EMAIL_PASSWORD: str = os.getenv('EMAIL_PASSWORD', '')
    ALERT_RECIPIENTS: List[str] = os.getenv('ALERT_RECIPIENTS', '').split(',') if os.getenv('ALERT_RECIPIENTS') else []
    
    # Slack Configuration
    SLACK_WEBHOOK_URL: str = os.getenv('SLACK_WEBHOOK_URL', '')
    
    # Processing Configuration
    BATCH_SIZE: int = int(os.getenv('BATCH_SIZE', '1000'))  # Process logs in batches
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY: int = int(os.getenv('RETRY_DELAY', '60'))  # seconds
    
    # Supported Languages
    SUPPORTED_LANGUAGES: List[str] = [
        'en', 'es', 'fr', 'de', 'it', 'ja', 'zh', 'ru', 'ar', 'hi', 'he', 'tt', 'uk', 'am', 'hin'
    ]
    
    # Language Categories for Analysis
    SEEN_LANGUAGES: List[str] = ['en', 'es', 'de', 'ar', 'hi', 'zh', 'ru', 'uk', 'am']
    UNSEEN_LANGUAGES: List[str] = ['fr', 'it', 'hin', 'ja', 'tt', 'he']
    
    @classmethod
    def get_log_filter(cls) -> str:
        """Get the log filter for Cloud Logging"""
        return f"""
        resource.type="gce_instance" AND
        jsonPayload.request_id!="" AND
        logName="projects/{cls.GCP_PROJECT_ID}/logs/{cls.LOG_NAME}"
        """
    
    @classmethod
    def get_baseline_timedelta(cls) -> timedelta:
        """Get baseline time delta"""
        return timedelta(hours=cls.BASELINE_HOURS)
    
    @classmethod
    def get_min_baseline_timedelta(cls) -> timedelta:
        """Get minimum baseline time delta"""
        return timedelta(hours=cls.MIN_BASELINE_HOURS)
    
    @classmethod
    def get_log_retention_timedelta(cls) -> timedelta:
        """Get log retention time delta"""
        return timedelta(hours=cls.LOG_RETENTION_HOURS)
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        errors = []
        
        if not cls.GCP_PROJECT_ID:
            errors.append("GCP_PROJECT_ID is required")
        
        if not cls.CREDENTIALS_PATH:
            errors.append("CREDENTIALS_PATH is required")
        
        if cls.ENABLE_EMAIL_ALERTS and not cls.EMAIL_USER:
            errors.append("EMAIL_USER is required when email alerts are enabled")
        
        if cls.ENABLE_SLACK_ALERTS and not cls.SLACK_WEBHOOK_URL:
            errors.append("SLACK_WEBHOOK_URL is required when Slack alerts are enabled")
        
        if cls.DETECTION_THRESHOLD_MEDIUM >= cls.DETECTION_THRESHOLD_HIGH:
            errors.append("DETECTION_THRESHOLD_MEDIUM must be less than DETECTION_THRESHOLD_HIGH")
        
        if cls.MIN_BASELINE_HOURS >= cls.BASELINE_HOURS:
            errors.append("MIN_BASELINE_HOURS must be less than BASELINE_HOURS")
        
        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration (excluding sensitive data)"""
        print("=== Data Shift Detection Service Configuration ===")
        print(f"GCP Project ID: {cls.GCP_PROJECT_ID}")
        print(f"Log Name: {cls.LOG_NAME}")
        print(f"Detection Thresholds: {cls.DETECTION_THRESHOLD_MEDIUM}% / {cls.DETECTION_THRESHOLD_HIGH}%")
        print(f"Baseline Hours: {cls.BASELINE_HOURS}")
        print(f"Grafana URL: {cls.GRAFANA_URL}")
        print(f"Email Alerts: {'Enabled' if cls.ENABLE_EMAIL_ALERTS else 'Disabled'}")
        print(f"Slack Alerts: {'Enabled' if cls.ENABLE_SLACK_ALERTS else 'Disabled'}")
        print(f"BigQuery Storage: {'Enabled' if cls.USE_BIGQUERY_STORAGE else 'Disabled'}")
        print(f"Supported Languages: {', '.join(cls.SUPPORTED_LANGUAGES)}")
        print("=" * 50)
