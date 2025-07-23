import logging
import statistics
from typing import List, Dict, Any
from collections import Counter
from evaluation.evaluate import eval
logger = logging.getLogger(__name__)

class MetricsCalculator:
    def __init__(self):
        pass
    
    def calculate_text_length_metrics(self, log_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate text length statistics from log data
        
        Args:
            log_data: List of log entries with text_length field
            
        Returns:
            Dictionary with text length metrics
        """
        if not log_data:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0,
                'count': 0
            }
        
        lengths = [entry['text_length'] for entry in log_data if 'text_length' in entry]
        
        if not lengths:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0,
                'count': 0
            }
        
        return {
            'mean': statistics.mean(lengths),
            'std': statistics.stdev(lengths) if len(lengths) > 1 else 0.0,
            'min': min(lengths),
            'max': max(lengths),
            'median': statistics.median(lengths),
            'count': len(lengths)
        }
    
    def calculate_language_distribution(self, log_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate language distribution from log data
        
        Args:
            log_data: List of log entries with language_id field
            
        Returns:
            Dictionary with language distribution percentages
        """
        if not log_data:
            return {}
        
        languages = [entry['language_id'] for entry in log_data if 'language_id' in entry]
        
        if not languages:
            return {}
        
        language_counts = Counter(languages)
        total_count = len(languages)
        
        # Convert to percentages
        language_distribution = {
            lang: (count / total_count) * 100
            for lang, count in language_counts.items()
        }
        
        return language_distribution
    
    def calculate_request_volume(self, log_data: List[Dict[str, Any]]) -> float:
        """
        Calculate request volume (requests per minute)
        
        Args:
            log_data: List of log entries
            
        Returns:
            Average requests per minute
        """
        if not log_data:
            return 0.0
        
        # Group by minute
        timestamps = [entry['timestamp'] for entry in log_data if 'timestamp' in entry]
        
        if not timestamps:
            return 0.0
        
        # Calculate time span in minutes
        start_time = min(timestamps)
        end_time = max(timestamps)
        time_span_minutes = (end_time - start_time).total_seconds() / 60.0
        
        if time_span_minutes <= 0:
            time_span_minutes = 1.0  # Avoid division by zero
        
        requests_per_minute = len(log_data) / time_span_minutes
        
        return requests_per_minute
    
    def calculate_data_shift(self, current_metrics: Dict[str, Any], baseline_metrics: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate data shift metrics by comparing current to baseline
        
        Args:
            current_metrics: Current period metrics
            baseline_metrics: Baseline metrics
            
        Returns:
            Dictionary with shift percentages
        """
        shift_metrics = {}
        
        # Calculate text length change
        current_text_mean = current_metrics.get('text_length', {}).get('mean', 0)
        baseline_text_mean = baseline_metrics.get('avg_text_length', 0)
        
        if baseline_text_mean > 0:
            shift_metrics['text_length_change'] = ((current_text_mean - baseline_text_mean) / baseline_text_mean) * 100
        else:
            shift_metrics['text_length_change'] = 0.0
        
        # Calculate language distribution change
        current_lang_dist = current_metrics.get('language_distribution', {})
        baseline_lang_dist = baseline_metrics.get('language_distribution', {})
        
        shift_metrics['language_distribution_change'] = self._calculate_distribution_change(
            current_lang_dist, baseline_lang_dist
        )
        
        # Calculate request volume change
        current_volume = current_metrics.get('request_volume', 0)
        baseline_volume = baseline_metrics.get('avg_request_volume', 0)
        
        if baseline_volume > 0:
            shift_metrics['request_volume_change'] = ((current_volume - baseline_volume) / baseline_volume) * 100
        else:
            shift_metrics['request_volume_change'] = 0.0
        
        return shift_metrics
    
    def _calculate_distribution_change(self, current_dist: Dict[str, float], baseline_dist: Dict[str, float]) -> float:
        """
        Calculate the change in distribution using Jensen-Shannon divergence approximation
        
        Args:
            current_dist: Current distribution
            baseline_dist: Baseline distribution
            
        Returns:
            Percentage change in distribution
        """
        if not current_dist or not baseline_dist:
            return 0.0
        
        # Get all unique languages
        all_languages = set(current_dist.keys()) | set(baseline_dist.keys())
        
        if not all_languages:
            return 0.0
        
        # Calculate simple percentage difference
        total_diff = 0.0
        for lang in all_languages:
            current_pct = current_dist.get(lang, 0.0)
            baseline_pct = baseline_dist.get(lang, 0.0)
            total_diff += abs(current_pct - baseline_pct)
        
        # Return average absolute difference
        return total_diff / len(all_languages)
    
    def calculate_model_performance(self, log_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate model performance metrics from log data
        
        Args:
            log_data: List of log entries with model performance fields
            
        Returns:
            Dictionary with model performance metrics
        """
        logger.info(f"{log_data[0]}")
        logger.info(f"Calculating model performance from {len(log_data)} log entries")
        input_texts = [entry['input_text'] for entry in log_data if 'input_text' in entry]
        output_texts = [entry['detoxified_text'] for entry in log_data if 'detoxified_text' in entry]
        language_ids = [entry['language_id'] for entry in log_data if 'language_id' in entry]
        # logger.info(f"Input texts: {input_texts}")
        # logger.info(f"Output texts: {output_texts}")
        results = eval(input_texts, output_texts, reference_texts=None)
        logger.info(f"Model performance calculated: {results}")
        # group results by language
        import pandas as pd
        results_df = pd.DataFrame({
            # 'J Score': results['J'],
            'Toxicity': results['STA'],
            'Similarity': results['SIM'],
            # 'Fluency': results['XCOMET']
        })
        results_df['language_id'] = language_ids
        results_df = results_df.groupby('language_id').agg(['mean', 'std']).reset_index()
        results_df.fillna(0, inplace=True)
        results_dict = results_df.set_index('language_id').T.to_dict()
        return results_dict

    def process_log_data(self, log_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process log data and calculate all metrics
        
        Args:
            log_data: List of log entries
            
        Returns:
            Dictionary with all calculated metrics
        """
        logger.info(f"Processing {len(log_data)} log entries")
        
        metrics = {
            'text_length': self.calculate_text_length_metrics(log_data),
            'language_distribution': self.calculate_language_distribution(log_data),
            'request_volume': self.calculate_request_volume(log_data),
            'model_performance': self.calculate_model_performance(log_data),
            'total_requests': len(log_data)
        }
        
        logger.info(f"Calculated metrics: {metrics}")
        return metrics
if __name__ == "__main__":
    # Example usage
    calculator = MetricsCalculator()
    example_log_data = [
        {
            'timestamp': '2023-10-01T12:00:00Z',
            'input_text': 'Hello world',
            'language_id': 'en',
            'text_length': 11,
            'output_text': 'Hello world',
            'request_id': '12345',
            'model_used': 'model_v1'
        },
        {
            'timestamp': '2023-10-01T12:01:00Z',
            'input_text': 'Bonjour le monde',
            'language_id': 'fr',
            'text_length': 17,
            'output_text': 'Bonjour le monde',
            'request_id': '12346',
            'model_used': 'model_v1'
        }
    ]
    
    metrics = calculator.process_log_data(example_log_data)
    print(metrics['model_performance'])
    model_performance = metrics['model_performance']
    for language in model_performance:
        for (metric, type), value in model_performance[language].items():
            print(f"Language: {language}, Metric: {type}, Value: {value}")
