"""
Alert manager for handling email and Slack notifications
"""
import logging
import smtplib
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import Config
from .shift_detector import ShiftAlert

class AlertManager:
    """Handles alert notifications via email and Slack"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.email_enabled = Config.ENABLE_EMAIL_ALERTS
        self.slack_enabled = Config.ENABLE_SLACK_ALERTS
        
        if self.email_enabled:
            self.logger.info("Email alerts enabled")
        if self.slack_enabled:
            self.logger.info("Slack alerts enabled")
    
    def send_alerts(self, alerts: List[ShiftAlert]) -> bool:
        """
        Send alerts via all enabled channels
        
        Args:
            alerts: List of shift alerts to send
            
        Returns:
            True if at least one channel succeeded, False otherwise
        """
        if not alerts:
            self.logger.info("No alerts to send")
            return True
        
        success = True
        
        try:
            # Filter alerts by severity (only send medium and high)
            significant_alerts = [
                alert for alert in alerts 
                if alert.alert_severity in ['MEDIUM', 'HIGH']
            ]
            
            if not significant_alerts:
                self.logger.info("No significant alerts to send")
                return True
            
            # Send email alerts
            if self.email_enabled:
                email_success = self._send_email_alerts(significant_alerts)
                if not email_success:
                    success = False
            
            # Send Slack alerts
            if self.slack_enabled:
                slack_success = self._send_slack_alerts(significant_alerts)
                if not slack_success:
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending alerts: {e}")
            return False
    
    def _send_email_alerts(self, alerts: List[ShiftAlert]) -> bool:
        """Send alerts via email"""
        if not Config.EMAIL_USER or not Config.EMAIL_PASSWORD or not Config.ALERT_RECIPIENTS:
            self.logger.warning("Email configuration incomplete, skipping email alerts")
            return False
        
        try:
            # Create email message
            subject = self._create_email_subject(alerts)
            body = self._create_email_body(alerts)
            
            # Setup email
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_USER
            msg['To'] = ', '.join(Config.ALERT_RECIPIENTS)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            
            for recipient in Config.ALERT_RECIPIENTS:
                if recipient.strip():
                    server.send_message(msg, to_addrs=[recipient.strip()])
            
            server.quit()
            
            self.logger.info(f"Email alerts sent to {len(Config.ALERT_RECIPIENTS)} recipients")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alerts: {e}")
            return False
    
    def _send_slack_alerts(self, alerts: List[ShiftAlert]) -> bool:
        """Send alerts via Slack"""
        if not Config.SLACK_WEBHOOK_URL:
            self.logger.warning("Slack webhook URL not configured, skipping Slack alerts")
            return False
        
        try:
            # Create Slack message
            message = self._create_slack_message(alerts)
            
            # Send to Slack
            response = requests.post(
                Config.SLACK_WEBHOOK_URL,
                json=message,
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.info("Slack alerts sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Slack alerts: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to send Slack alerts: {e}")
            return False
    
    def _create_email_subject(self, alerts: List[ShiftAlert]) -> str:
        """Create email subject line"""
        high_alerts = [a for a in alerts if a.alert_severity == 'HIGH']
        medium_alerts = [a for a in alerts if a.alert_severity == 'MEDIUM']
        
        if high_alerts:
            return f"🚨 HIGH PRIORITY: Language Distribution Shift Alert ({len(high_alerts)} high, {len(medium_alerts)} medium)"
        else:
            return f"⚠️ Language Distribution Shift Alert ({len(medium_alerts)} medium)"
    
    def _create_email_body(self, alerts: List[ShiftAlert]) -> str:
        """Create email body"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        body = f"""Language Distribution Shift Alert Report
Generated: {timestamp}
Project: {Config.GCP_PROJECT_ID}

SUMMARY:
- Total alerts: {len(alerts)}
- High severity: {len([a for a in alerts if a.alert_severity == 'HIGH'])}
- Medium severity: {len([a for a in alerts if a.alert_severity == 'MEDIUM'])}

ALERT DETAILS:
"""
        
        # Group alerts by severity
        high_alerts = [a for a in alerts if a.alert_severity == 'HIGH']
        medium_alerts = [a for a in alerts if a.alert_severity == 'MEDIUM']
        
        if high_alerts:
            body += "\n🔴 HIGH SEVERITY ALERTS:\n"
            for alert in high_alerts:
                body += self._format_alert_for_email(alert)
        
        if medium_alerts:
            body += "\n🟡 MEDIUM SEVERITY ALERTS:\n"
            for alert in medium_alerts:
                body += self._format_alert_for_email(alert)
        
        body += f"""
\nMONITORING DASHBOARD:
{Config.GRAFANA_URL}/d/language-distribution-monitoring

DETECTION CONFIGURATION:
- Baseline period: {Config.BASELINE_HOURS} hours
- Medium threshold: {Config.DETECTION_THRESHOLD_MEDIUM}%
- High threshold: {Config.DETECTION_THRESHOLD_HIGH}%

---
This is an automated alert from the Data Shift Detection Service.
"""
        
        return body
    
    def _format_alert_for_email(self, alert: ShiftAlert) -> str:
        """Format a single alert for email"""
        analysis_time = alert.analysis_hour.strftime('%Y-%m-%d %H:%M')
        
        if alert.shift_type == 'new_language':
            return f"  • {alert.language_id}: NEW LANGUAGE DETECTED ({alert.current_percentage:.1f}%) at {analysis_time}\n"
        elif alert.shift_type == 'disappeared':
            return f"  • {alert.language_id}: LANGUAGE DISAPPEARED (was {alert.baseline_percentage:.1f}%) at {analysis_time}\n"
        else:
            direction = "increased" if alert.percentage_change > 0 else "decreased"
            return f"  • {alert.language_id}: {direction} by {abs(alert.percentage_change):.1f}% ({alert.baseline_percentage:.1f}% → {alert.current_percentage:.1f}%) at {analysis_time}\n"
    
    def _create_slack_message(self, alerts: List[ShiftAlert]) -> Dict:
        """Create Slack message payload"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Determine color based on alert severity
        high_alerts = [a for a in alerts if a.alert_severity == 'HIGH']
        color = 'danger' if high_alerts else 'warning'
        
        # Create main message
        main_text = f"🚨 Language Distribution Shift Alert ({len(alerts)} alerts)"
        
        # Create attachment with details
        attachment_text = f"*Generated:* {timestamp}\n*Project:* {Config.GCP_PROJECT_ID}\n\n"
        
        # Add alert details
        if high_alerts:
            attachment_text += "*🔴 HIGH SEVERITY ALERTS:*\n"
            for alert in high_alerts:
                attachment_text += self._format_alert_for_slack(alert)
            attachment_text += "\n"
        
        medium_alerts = [a for a in alerts if a.alert_severity == 'MEDIUM']
        if medium_alerts:
            attachment_text += "*🟡 MEDIUM SEVERITY ALERTS:*\n"
            for alert in medium_alerts:
                attachment_text += self._format_alert_for_slack(alert)
        
        # Add dashboard link
        attachment_text += f"\n<{Config.GRAFANA_URL}|View Monitoring Dashboard>"
        
        return {
            'text': main_text,
            'attachments': [
                {
                    'color': color,
                    'text': attachment_text,
                    'footer': f'Data Shift Detection Service - {Config.GCP_PROJECT_ID}',
                    'ts': int(datetime.now().timestamp())
                }
            ]
        }
    
    def _format_alert_for_slack(self, alert: ShiftAlert) -> str:
        """Format a single alert for Slack"""
        analysis_time = alert.analysis_hour.strftime('%H:%M')
        
        if alert.shift_type == 'new_language':
            return f"• `{alert.language_id}`: NEW LANGUAGE ({alert.current_percentage:.1f}%) at {analysis_time}\n"
        elif alert.shift_type == 'disappeared':
            return f"• `{alert.language_id}`: DISAPPEARED (was {alert.baseline_percentage:.1f}%) at {analysis_time}\n"
        else:
            direction = "↑" if alert.percentage_change > 0 else "↓"
            return f"• `{alert.language_id}`: {direction} {abs(alert.percentage_change):.1f}% ({alert.baseline_percentage:.1f}% → {alert.current_percentage:.1f}%) at {analysis_time}\n"
    
    def send_health_alert(self, status: str, message: str) -> bool:
        """
        Send health status alert
        
        Args:
            status: Health status ('healthy', 'warning', 'error')
            message: Alert message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create simple alert for health status
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            if self.email_enabled and status == 'error':
                self._send_health_email(status, message, timestamp)
            
            if self.slack_enabled:
                self._send_health_slack(status, message, timestamp)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending health alert: {e}")
            return False
    
    def _send_health_email(self, status: str, message: str, timestamp: str):
        """Send health alert via email"""
        try:
            subject = f"Data Shift Service Health Alert - {status.upper()}"
            body = f"""Data Shift Detection Service Health Alert

Status: {status.upper()}
Time: {timestamp}
Message: {message}

This is an automated health alert from the Data Shift Detection Service.
"""
            
            msg = MIMEMultipart()
            msg['From'] = Config.EMAIL_USER
            msg['To'] = ', '.join(Config.ALERT_RECIPIENTS)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            
            for recipient in Config.ALERT_RECIPIENTS:
                if recipient.strip():
                    server.send_message(msg, to_addrs=[recipient.strip()])
            
            server.quit()
            
        except Exception as e:
            self.logger.error(f"Failed to send health email: {e}")
    
    def _send_health_slack(self, status: str, message: str, timestamp: str):
        """Send health alert via Slack"""
        try:
            color_map = {
                'healthy': 'good',
                'warning': 'warning',
                'error': 'danger'
            }
            
            emoji_map = {
                'healthy': '✅',
                'warning': '⚠️',
                'error': '🚨'
            }
            
            payload = {
                'text': f"{emoji_map.get(status, '❓')} Data Shift Service Health Alert",
                'attachments': [
                    {
                        'color': color_map.get(status, 'warning'),
                        'text': f"*Status:* {status.upper()}\n*Time:* {timestamp}\n*Message:* {message}",
                        'footer': f'Data Shift Detection Service - {Config.GCP_PROJECT_ID}',
                        'ts': int(datetime.now().timestamp())
                    }
                ]
            }
            
            response = requests.post(
                Config.SLACK_WEBHOOK_URL,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                self.logger.error(f"Failed to send health Slack alert: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Failed to send health Slack alert: {e}")
    
    def test_notifications(self) -> Dict[str, bool]:
        """
        Test notification channels
        
        Returns:
            Dictionary with test results for each channel
        """
        results = {}
        
        # Test email
        if self.email_enabled:
            try:
                test_alert = ShiftAlert(
                    alert_timestamp=datetime.now(),
                    analysis_hour=datetime.now(),
                    language_id='test',
                    current_percentage=50.0,
                    baseline_percentage=30.0,
                    percentage_change=66.67,
                    alert_severity='MEDIUM',
                    current_request_count=50,
                    baseline_request_count=30,
                    shift_type='test'
                )
                
                results['email'] = self._send_email_alerts([test_alert])
            except Exception as e:
                self.logger.error(f"Email test failed: {e}")
                results['email'] = False
        
        # Test Slack
        if self.slack_enabled:
            try:
                test_message = {
                    'text': 'Test message from Data Shift Detection Service',
                    'attachments': [
                        {
                            'color': 'good',
                            'text': 'This is a test notification to verify Slack integration.',
                            'footer': f'Data Shift Detection Service - {Config.GCP_PROJECT_ID}',
                            'ts': int(datetime.now().timestamp())
                        }
                    ]
                }
                
                response = requests.post(
                    Config.SLACK_WEBHOOK_URL,
                    json=test_message,
                    timeout=30
                )
                
                results['slack'] = response.status_code == 200
            except Exception as e:
                self.logger.error(f"Slack test failed: {e}")
                results['slack'] = False
        
        return results
