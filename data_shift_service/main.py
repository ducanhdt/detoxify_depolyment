"""
Main entry point for the Data Shift Detection Service
"""
import logging
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from .config import Config
from .log_processor import LogProcessor
from .shift_detector import ShiftDetector
from .grafana_pusher import GrafanaPusher
from .alert_manager import AlertManager
from .metrics_exporter import MetricsExporter

class DataShiftService:
    """Main service class for data shift detection"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scheduler = AsyncIOScheduler()
        self.running = False
        
        # Initialize components
        self.log_processor = LogProcessor()
        self.shift_detector = ShiftDetector(self.log_processor)
        self.grafana_pusher = GrafanaPusher()
        self.alert_manager = AlertManager()
        self.metrics_exporter = MetricsExporter()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.scheduler.running:
            self.scheduler.shutdown()
        sys.exit(0)
    
    async def start(self):
        """Start the service"""
        self.logger.info("Starting Data Shift Detection Service")
        
        # Validate configuration
        if not Config.validate_config():
            self.logger.error("Configuration validation failed")
            return False
        
        Config.print_config()
        
        # Start metrics server
        self.metrics_exporter.run_server(host='0.0.0.0', port=8080)
        
        # Perform health checks
        if not await self._health_check():
            self.logger.error("Health check failed")
            return False
        
        # Setup scheduled jobs
        self._setup_scheduler()
        
        # Start scheduler
        self.scheduler.start()
        self.running = True
        
        self.logger.info("Service started successfully")
        
        # Send startup notification
        await self._send_startup_notification()
        
        # Keep the service running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            await self.stop()
        
        return True
    
    async def stop(self):
        """Stop the service"""
        self.logger.info("Stopping Data Shift Detection Service")
        
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        # Send shutdown notification
        await self._send_shutdown_notification()
        
        self.logger.info("Service stopped")
    
    def _setup_scheduler(self):
        """Setup scheduled jobs"""
        # Main analysis job - runs every hour
        self.scheduler.add_job(
            self._run_hourly_analysis,
            CronTrigger(minute=Config.SCHEDULE_MINUTE),
            id='hourly_analysis',
            name='Hourly Language Distribution Analysis',
            max_instances=1,
            coalesce=True
        )
        
        # Log cleanup job - runs daily at 2 AM
        self.scheduler.add_job(
            self._cleanup_old_logs,
            CronTrigger(hour=2, minute=0),
            id='log_cleanup',
            name='Old Log Cleanup',
            max_instances=1,
            coalesce=True
        )
        
        # Health check job - runs every 30 minutes
        self.scheduler.add_job(
            self._periodic_health_check,
            CronTrigger(minute='*/30'),
            id='health_check',
            name='Periodic Health Check',
            max_instances=1,
            coalesce=True
        )
        
        # Grafana cleanup job - runs weekly
        self.scheduler.add_job(
            self._cleanup_grafana_annotations,
            CronTrigger(day_of_week=0, hour=3, minute=0),
            id='grafana_cleanup',
            name='Grafana Annotations Cleanup',
            max_instances=1,
            coalesce=True
        )
        
        self.logger.info("Scheduled jobs configured")
    
    async def _run_hourly_analysis(self):
        """Run the hourly language distribution analysis"""
        self.logger.info("Starting hourly analysis")
        
        analysis_start_time = datetime.now()
        
        try:
            # Analyze the previous hour (current hour - 1)
            current_time = datetime.now()
            analysis_hour = current_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            
            self.logger.info(f"Analyzing hour: {analysis_hour}")
            
            # Get language distribution for the hour
            distributions = self.shift_detector.analyze_hourly_distribution(analysis_hour)
            
            if not distributions:
                self.logger.warning(f"No data available for hour {analysis_hour}")
                self.metrics_exporter.record_error('no_data_available')
                return
            
            # Update metrics with distribution data
            self.metrics_exporter.update_language_distribution(distributions)
            
            # Detect shifts
            alerts = self.shift_detector.detect_shifts(analysis_hour)
            
            # Update metrics with alert data
            self.metrics_exporter.update_shift_alerts(alerts)
            
            # Push to Grafana
            grafana_success = self.grafana_pusher.push_language_distribution(distributions)
            if not grafana_success:
                self.logger.warning("Failed to push distribution data to Grafana")
                self.metrics_exporter.record_error('grafana_push_failed')
            
            # Push alerts to Grafana
            if alerts:
                alert_success = self.grafana_pusher.push_shift_alerts(alerts)
                if not alert_success:
                    self.logger.warning("Failed to push alerts to Grafana")
                    self.metrics_exporter.record_error('grafana_alert_push_failed')
            
            # Send notifications for significant alerts
            notification_success = self.alert_manager.send_alerts(alerts)
            if not notification_success:
                self.logger.warning("Failed to send alert notifications")
                self.metrics_exporter.record_error('notification_failed')
            
            # Update service health and timestamp
            self.metrics_exporter.update_service_health(True)
            self.metrics_exporter.update_last_analysis_timestamp(analysis_hour)
            
            # Record analysis duration
            duration = (datetime.now() - analysis_start_time).total_seconds()
            self.metrics_exporter.record_analysis_duration('hourly_analysis', duration)
            
            # Log summary
            self.logger.info(f"Analysis complete: {len(distributions)} languages, {len(alerts)} alerts")
            
            # Store summary in Grafana
            summary = self.shift_detector.get_distribution_summary(analysis_hour)
            if summary:
                self.grafana_pusher.push_health_status({
                    'status': 'healthy',
                    'last_analysis': analysis_hour.isoformat(),
                    'summary': summary
                })
            
        except Exception as e:
            self.logger.error(f"Error in hourly analysis: {e}")
            
            # Record error in metrics
            self.metrics_exporter.record_error('hourly_analysis_failed')
            self.metrics_exporter.update_service_health(False)
            
            # Send error alert
            self.alert_manager.send_health_alert(
                'error',
                f"Hourly analysis failed: {str(e)}"
            )
    
    async def _cleanup_old_logs(self):
        """Cleanup old logs to save costs"""
        self.logger.info("Starting log cleanup")
        
        try:
            cutoff_time = datetime.now() - Config.get_log_retention_timedelta()
            
            success = self.log_processor.delete_old_logs(cutoff_time)
            
            if success:
                self.logger.info("Log cleanup completed successfully")
            else:
                self.logger.warning("Log cleanup failed")
                
        except Exception as e:
            self.logger.error(f"Error in log cleanup: {e}")
            
            # Send error alert
            self.alert_manager.send_health_alert(
                'error',
                f"Log cleanup failed: {str(e)}"
            )
    
    async def _periodic_health_check(self):
        """Perform periodic health check"""
        self.logger.debug("Performing periodic health check")
        
        try:
            health_status = await self._health_check()
            
            if health_status:
                self.logger.debug("Health check passed")
                
                # Push healthy status to Grafana
                self.grafana_pusher.push_health_status({
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat(),
                    'message': 'All systems operational'
                })
            else:
                self.logger.warning("Health check failed")
                
                # Send warning alert
                self.alert_manager.send_health_alert(
                    'warning',
                    'Health check failed - some components may be down'
                )
                
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
    
    async def _cleanup_grafana_annotations(self):
        """Cleanup old Grafana annotations"""
        self.logger.info("Cleaning up old Grafana annotations")
        
        try:
            success = self.grafana_pusher.clear_old_annotations(days=7)
            
            if success:
                self.logger.info("Grafana annotations cleanup completed")
            else:
                self.logger.warning("Grafana annotations cleanup failed")
                
        except Exception as e:
            self.logger.error(f"Error in Grafana cleanup: {e}")
    
    async def _health_check(self) -> bool:
        """Perform comprehensive health check"""
        self.logger.debug("Performing health check")
        
        try:
            # Check log processor
            log_health = self.log_processor.health_check()
            
            # Check Grafana
            grafana_health = self.grafana_pusher.health_check()
            
            # Check configuration
            config_health = Config.validate_config()
            
            overall_health = log_health and grafana_health and config_health
            
            if not overall_health:
                self.logger.warning(f"Health check results: Log={log_health}, Grafana={grafana_health}, Config={config_health}")
            
            return overall_health
            
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return False
    
    async def _send_startup_notification(self):
        """Send service startup notification"""
        try:
            self.alert_manager.send_health_alert(
                'healthy',
                'Data Shift Detection Service started successfully'
            )
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}")
    
    async def _send_shutdown_notification(self):
        """Send service shutdown notification"""
        try:
            self.alert_manager.send_health_alert(
                'warning',
                'Data Shift Detection Service is shutting down'
            )
        except Exception as e:
            self.logger.error(f"Failed to send shutdown notification: {e}")
    
    async def run_manual_analysis(self, hour: Optional[datetime] = None):
        """Run manual analysis for testing"""
        if hour is None:
            hour = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        
        self.logger.info(f"Running manual analysis for hour: {hour}")
        
        try:
            # Get distributions
            distributions = self.shift_detector.analyze_hourly_distribution(hour)
            
            # Detect shifts
            alerts = self.shift_detector.detect_shifts(hour)
            
            # Print results
            print(f"\n=== Analysis Results for {hour} ===")
            print(f"Language Distributions: {len(distributions)}")
            for dist in distributions:
                print(f"  {dist.language_id}: {dist.percentage:.1f}% ({dist.request_count} requests)")
            
            print(f"\nShift Alerts: {len(alerts)}")
            for alert in alerts:
                print(f"  {alert.language_id}: {alert.shift_type} - {alert.alert_severity} ({alert.percentage_change:.1f}%)")
            
            return distributions, alerts
            
        except Exception as e:
            self.logger.error(f"Manual analysis failed: {e}")
            return [], []
    
    async def test_notifications(self):
        """Test notification channels"""
        self.logger.info("Testing notification channels")
        
        try:
            results = self.alert_manager.test_notifications()
            
            print("\n=== Notification Test Results ===")
            for channel, success in results.items():
                status = "✅ PASSED" if success else "❌ FAILED"
                print(f"{channel.upper()}: {status}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Notification test failed: {e}")
            return {}

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Set more verbose logging for our modules
    logging.getLogger('data_shift_service').setLevel(logging.DEBUG)
    
    # Reduce noise from external libraries
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

async def main():
    """Main entry point"""
    setup_logging()
    
    service = DataShiftService()
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())
