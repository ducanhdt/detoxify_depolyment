"""
Language distribution shift detection module
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

from .config import Config
from .log_processor import LogProcessor, InferenceLog

@dataclass
class LanguageDistribution:
    """Data class for language distribution data"""
    hour_timestamp: datetime
    language_id: str
    request_count: int
    percentage: float
    total_requests_hour: int

@dataclass
class ShiftAlert:
    """Data class for shift alert information"""
    alert_timestamp: datetime
    analysis_hour: datetime
    language_id: str
    current_percentage: float
    baseline_percentage: float
    percentage_change: float
    alert_severity: str
    current_request_count: int
    baseline_request_count: int
    shift_type: str  # 'increase', 'decrease', 'new_language', 'disappeared'

class ShiftDetector:
    """Handles language distribution analysis and shift detection"""
    
    def __init__(self, log_processor: LogProcessor):
        self.logger = logging.getLogger(__name__)
        self.log_processor = log_processor
        self.cache = {}  # Simple cache for baseline data
    
    def analyze_hourly_distribution(self, hour: datetime) -> List[LanguageDistribution]:
        """
        Analyze language distribution for a specific hour
        
        Args:
            hour: The hour to analyze (should be truncated to hour precision)
            
        Returns:
            List of LanguageDistribution objects
        """
        self.logger.info(f"Analyzing language distribution for hour: {hour}")
        
        try:
            # Define time range for the hour
            start_time = hour.replace(minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1)
            
            # Fetch logs for the hour
            logs = self.log_processor.fetch_logs(start_time, end_time)
            
            if not logs:
                self.logger.warning(f"No logs found for hour: {hour}")
                return []
            
            # Count requests by language
            language_counts = defaultdict(int)
            total_requests = 0
            
            for log in logs:
                if log.language_id in Config.SUPPORTED_LANGUAGES:
                    language_counts[log.language_id] += 1
                    total_requests += 1
            
            # Calculate percentages and create distribution objects
            distributions = []
            for language_id, count in language_counts.items():
                percentage = (count / total_requests) * 100 if total_requests > 0 else 0
                
                distribution = LanguageDistribution(
                    hour_timestamp=start_time,
                    language_id=language_id,
                    request_count=count,
                    percentage=round(percentage, 2),
                    total_requests_hour=total_requests
                )
                distributions.append(distribution)
            
            self.logger.info(f"Analyzed {len(distributions)} languages for hour {hour}")
            return distributions
            
        except Exception as e:
            self.logger.error(f"Error analyzing hourly distribution: {e}")
            return []
    
    def get_baseline_distribution(self, reference_time: datetime) -> Dict[str, float]:
        """
        Get baseline language distribution (average over baseline period)
        
        Args:
            reference_time: The reference time for baseline calculation
            
        Returns:
            Dictionary mapping language_id to baseline percentage
        """
        self.logger.info(f"Calculating baseline distribution for reference time: {reference_time}")
        
        try:
            # Calculate baseline time range
            baseline_end = reference_time - timedelta(hours=1)  # Exclude current hour
            baseline_start = baseline_end - Config.get_baseline_timedelta()
            
            # Check cache
            cache_key = f"baseline_{baseline_start.isoformat()}_{baseline_end.isoformat()}"
            if cache_key in self.cache:
                self.logger.debug("Using cached baseline data")
                return self.cache[cache_key]
            
            # Fetch baseline logs
            baseline_logs = self.log_processor.fetch_logs(baseline_start, baseline_end)
            
            if not baseline_logs:
                self.logger.warning("No baseline logs found")
                return {}
            
            # Group logs by hour and calculate hourly distributions
            hourly_distributions = defaultdict(lambda: defaultdict(int))
            hourly_totals = defaultdict(int)
            
            for log in baseline_logs:
                if log.language_id in Config.SUPPORTED_LANGUAGES:
                    hour_key = log.timestamp.replace(minute=0, second=0, microsecond=0)
                    hourly_distributions[hour_key][log.language_id] += 1
                    hourly_totals[hour_key] += 1
            
            # Calculate average percentages across all hours
            language_hour_percentages = defaultdict(list)
            
            for hour_key, language_counts in hourly_distributions.items():
                hour_total = hourly_totals[hour_key]
                if hour_total > 0:
                    for language_id, count in language_counts.items():
                        percentage = (count / hour_total) * 100
                        language_hour_percentages[language_id].append(percentage)
            
            # Calculate baseline as average percentage across hours
            baseline_distribution = {}
            for language_id, percentages in language_hour_percentages.items():
                if len(percentages) >= Config.MIN_BASELINE_HOURS:
                    baseline_distribution[language_id] = statistics.mean(percentages)
            
            # Cache the result
            self.cache[cache_key] = baseline_distribution
            
            self.logger.info(f"Calculated baseline for {len(baseline_distribution)} languages")
            return baseline_distribution
            
        except Exception as e:
            self.logger.error(f"Error calculating baseline distribution: {e}")
            return {}
    
    def detect_shifts(self, current_hour: datetime) -> List[ShiftAlert]:
        """
        Detect language distribution shifts for the current hour
        
        Args:
            current_hour: The hour to analyze for shifts
            
        Returns:
            List of ShiftAlert objects
        """
        self.logger.info(f"Detecting shifts for hour: {current_hour}")
        
        try:
            # Get current hour distribution
            current_distributions = self.analyze_hourly_distribution(current_hour)
            if not current_distributions:
                self.logger.warning("No current distribution data available")
                return []
            
            # Convert to dictionary for easier lookup
            current_dist_dict = {
                dist.language_id: dist for dist in current_distributions
            }
            
            # Get baseline distribution
            baseline_dist = self.get_baseline_distribution(current_hour)
            if not baseline_dist:
                self.logger.warning("No baseline distribution data available")
                return []
            
            # Detect shifts
            alerts = []
            alert_timestamp = datetime.now()
            
            # Check all languages (current and baseline)
            all_languages = set(current_dist_dict.keys()) | set(baseline_dist.keys())
            
            for language_id in all_languages:
                current_pct = current_dist_dict.get(language_id, LanguageDistribution(
                    current_hour, language_id, 0, 0.0, 0
                )).percentage
                
                baseline_pct = baseline_dist.get(language_id, 0.0)
                
                # Calculate percentage change
                if baseline_pct > 0:
                    pct_change = ((current_pct - baseline_pct) / baseline_pct) * 100
                elif current_pct > 0:
                    pct_change = 999.99  # New language appeared
                else:
                    continue  # Both are 0, no change
                
                # Determine shift type and severity
                shift_type, severity = self._classify_shift(
                    current_pct, baseline_pct, pct_change
                )
                
                # Create alert if significant shift detected
                if severity != 'NONE':
                    current_dist = current_dist_dict.get(language_id)
                    current_count = current_dist.request_count if current_dist else 0
                    
                    # Calculate baseline request count (approximate)
                    baseline_count = int(baseline_pct * 
                                       (current_distributions[0].total_requests_hour / 100)
                                       if current_distributions else 0)
                    
                    alert = ShiftAlert(
                        alert_timestamp=alert_timestamp,
                        analysis_hour=current_hour,
                        language_id=language_id,
                        current_percentage=current_pct,
                        baseline_percentage=baseline_pct,
                        percentage_change=round(pct_change, 2),
                        alert_severity=severity,
                        current_request_count=current_count,
                        baseline_request_count=baseline_count,
                        shift_type=shift_type
                    )
                    alerts.append(alert)
            
            self.logger.info(f"Detected {len(alerts)} language distribution shifts")
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error detecting shifts: {e}")
            return []
    
    def _classify_shift(self, current_pct: float, baseline_pct: float, 
                       pct_change: float) -> Tuple[str, str]:
        """
        Classify the type and severity of a shift
        
        Args:
            current_pct: Current percentage
            baseline_pct: Baseline percentage
            pct_change: Percentage change
            
        Returns:
            Tuple of (shift_type, severity)
        """
        # Determine shift type
        if baseline_pct == 0 and current_pct > 0:
            shift_type = 'new_language'
        elif baseline_pct > 0 and current_pct == 0:
            shift_type = 'disappeared'
        elif pct_change > 0:
            shift_type = 'increase'
        else:
            shift_type = 'decrease'
        
        # Determine severity
        abs_change = abs(pct_change)
        
        if abs_change >= Config.DETECTION_THRESHOLD_HIGH:
            severity = 'HIGH'
        elif abs_change >= Config.DETECTION_THRESHOLD_MEDIUM:
            severity = 'MEDIUM'
        else:
            severity = 'NONE'
        
        # Special cases
        if shift_type in ['new_language', 'disappeared']:
            severity = 'HIGH'
        
        return shift_type, severity
    
    def get_distribution_summary(self, hour: datetime) -> Dict:
        """
        Get a summary of language distribution for a specific hour
        
        Args:
            hour: The hour to summarize
            
        Returns:
            Dictionary with distribution summary
        """
        try:
            distributions = self.analyze_hourly_distribution(hour)
            
            if not distributions:
                return {}
            
            # Calculate summary statistics
            total_requests = distributions[0].total_requests_hour
            languages_detected = len(distributions)
            
            # Top languages
            top_languages = sorted(distributions, key=lambda x: x.percentage, reverse=True)[:5]
            
            # Language categories
            seen_lang_pct = sum(d.percentage for d in distributions if d.language_id in Config.SEEN_LANGUAGES)
            unseen_lang_pct = sum(d.percentage for d in distributions if d.language_id in Config.UNSEEN_LANGUAGES)
            
            return {
                'hour': hour.isoformat(),
                'total_requests': total_requests,
                'languages_detected': languages_detected,
                'top_languages': [
                    {
                        'language': lang.language_id,
                        'percentage': lang.percentage,
                        'count': lang.request_count
                    }
                    for lang in top_languages
                ],
                'seen_languages_percentage': round(seen_lang_pct, 2),
                'unseen_languages_percentage': round(unseen_lang_pct, 2),
                'distribution_entropy': self._calculate_entropy(distributions)
            }
            
        except Exception as e:
            self.logger.error(f"Error creating distribution summary: {e}")
            return {}
    
    def _calculate_entropy(self, distributions: List[LanguageDistribution]) -> float:
        """
        Calculate Shannon entropy of language distribution
        
        Args:
            distributions: List of language distributions
            
        Returns:
            Entropy value
        """
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
    
    def clear_cache(self):
        """Clear the baseline cache"""
        self.cache.clear()
        self.logger.info("Cleared baseline cache")
