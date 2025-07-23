import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

from gcp_client import GCPLogClient
from metrics_calculator import MetricsCalculator
from monitoring import DataShiftMonitor
from evaluation.evaluate import eval

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics - Organized by category

# Global metric instances - create once
_text_length_metrics = None
_request_metrics = None
_change_metrics = None
_monitoring_metrics = None
_language_distribution = None
_model_performance_mean = None
_model_performance_std = None

def create_text_length_metrics():
    """Create text length related metrics"""
    global _text_length_metrics
    if _text_length_metrics is not None:
        return _text_length_metrics
    
    metrics = {}
    metric_configs = [
        ('mean', 'Current average text length'),
        ('std', 'Current text length standard deviation'),
        ('min', 'Current minimum text length'),
        ('max', 'Current maximum text length'),
        ('median', 'Current median text length'),
        ('count', 'Number of text length samples')
    ]
    
    for name, description in metric_configs:
        metrics[name] = Gauge(f'data_shift_text_length_{name}', description)
    
    _text_length_metrics = metrics
    return metrics

def create_request_metrics():
    """Create request volume related metrics"""
    global _request_metrics
    if _request_metrics is not None:
        return _request_metrics
    
    metrics = {
        'current_volume': Gauge('data_shift_current_request_volume', 'Current request volume (requests per minute)'),
        'total_requests': Gauge('data_shift_total_requests', 'Total number of requests in current analysis window')
    }
    _request_metrics = metrics
    return metrics

def create_change_metrics():
    """Create data shift change metrics"""
    global _change_metrics
    if _change_metrics is not None:
        return _change_metrics
    
    change_configs = [
        ('text_length_mean', 'Percentage change in average text length compared to baseline'),
        ('language_distribution', 'Percentage change in language distribution compared to baseline'),
        ('request_volume', 'Percentage change in request volume compared to baseline')
    ]
    
    metrics = {}
    for name, description in change_configs:
        metrics[name] = Gauge(f'data_shift_{name}_change', description)
    
    _change_metrics = metrics
    return metrics

def create_monitoring_metrics():
    """Create general monitoring metrics"""
    global _monitoring_metrics
    if _monitoring_metrics is not None:
        return _monitoring_metrics
    
    metrics = {
        'last_check_timestamp': Gauge('data_shift_last_check_timestamp', 'Timestamp of last data shift check'),
        'checks_total': Counter('monitoring_checks_total', 'Total number of monitoring checks performed')
    }
    _monitoring_metrics = metrics
    return metrics

def get_language_distribution_metric():
    """Get or create language distribution metric"""
    global _language_distribution
    if _language_distribution is None:
        _language_distribution = Gauge(
            'data_shift_language_distribution_percent',
            'Language distribution percentage',
            ['language']
        )
    return _language_distribution

def get_model_performance_metrics():
    """Get or create model performance metrics"""
    logger.info("Initializing model performance metrics")
    global _model_performance_mean, _model_performance_std
    if _model_performance_mean is None:
        _model_performance_mean = Gauge(
            'model_performance_mean',
            'Model performance metrics for different languages',
            ['language', 'metric']
        )
    if _model_performance_std is None:
        _model_performance_std = Gauge(
            'model_performance_std',
            'Model performance standard deviation for different languages',
            ['language', 'metric']
        )
    logger.info("Model performance metrics initialized")
    return _model_performance_mean, _model_performance_std

# Initialize metric groups
text_length_metrics = create_text_length_metrics()
request_metrics = create_request_metrics()
change_metrics = create_change_metrics()
monitoring_metrics = create_monitoring_metrics()

# Language distribution metric (needs labels)
language_distribution = get_language_distribution_metric()

model_performance_mean, model_performance_std = get_model_performance_metrics()


# Global variables
monitor: Optional[DataShiftMonitor] = None
monitoring_active = False
last_check_result: Optional[Dict[str, Any]] = None

def update_prometheus_metrics(result: Dict[str, Any]):
    """Helper function to update all Prometheus metrics from monitoring result"""
    current_metrics_data = result.get('current_metrics', {})
    
    # Update text length metrics
    text_length_data = current_metrics_data.get('text_length', {})
    for metric_name, gauge in text_length_metrics.items():
        gauge.set(text_length_data.get(metric_name, 0))
    
    # Update request volume metrics
    request_metrics['current_volume'].set(current_metrics_data.get('request_volume', 0))
    request_metrics['total_requests'].set(current_metrics_data.get('total_requests', 0))
    
    # Update language distribution metrics
    lang_dist_data = current_metrics_data.get('language_distribution', {})
    language_distribution._metrics.clear()
    for language, percentage in lang_dist_data.items():
        language_distribution.labels(language=language).set(percentage)
    
    # Update change metrics
    change_values = {
        'text_length_mean': result.get('text_length_change', 0),
        'language_distribution': result.get('language_distribution_change', 0),
        'request_volume': result.get('request_volume_change', 0)
    }
    
    for metric_name, value in change_values.items():
        change_metrics[metric_name].set(value)
    
    monitoring_metrics['last_check_timestamp'].set(datetime.now().timestamp())

    # Update model performance metrics
    model_performance = current_metrics_data.get('model_performance', {})
    for language in model_performance:
        for (metric, type), value in model_performance[language].items():
            if type == 'mean':
                model_performance_mean.labels(language=language, metric=metric).set(value)
            if type == 'std':
                model_performance_std.labels(language=language, metric=metric).set(value)

class BaselineUpdate(BaseModel):
    avg_text_length: float
    text_length_std: float
    language_distribution: Dict[str, float]
    avg_request_volume: float

app = FastAPI(title="Data Shift Monitoring Service", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    global monitor, monitoring_active
    
    try:
        # Initialize monitor
        monitor = DataShiftMonitor()
        # start evaluation service
        
        logger.info("Starting Data Shift Monitoring Service...")
        original_texts = ["What the hell is this?", "This is a test sentence."]
        rewritten_texts = ["What is this?", "This is a test."]
        reference_texts = None

        results = eval(original_texts, rewritten_texts, reference_texts)
        logger.info(f"Evaluation results: {results}")

        # Start background monitoring
        monitoring_active = True
        asyncio.create_task(background_monitoring())
        
        logger.info("Data Shift Monitoring Service started successfully")
    except Exception as e:
        logger.error(f"Failed to start monitoring service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    global monitoring_active
    monitoring_active = False
    logger.info("Data Shift Monitoring Service shutting down")

async def background_monitoring():
    """Background task that runs monitoring checks every 1 minute"""
    global last_check_result
    
    while monitoring_active:
        try:
            if monitor:
                logger.info("Running data shift check...")
                result = await monitor.check_data_shift()
                last_check_result = result
                
                # Update all Prometheus metrics
                update_prometheus_metrics(result)
                
                monitoring_metrics['checks_total'].inc()
                
                logger.info(f"Data shift check completed: {result}")
            
            # Wait 1 minute before next check
            await asyncio.sleep(5*60)
            
        except Exception as e:
            logger.error(f"Error in background monitoring: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await asyncio.sleep(5*60)  # Wait before retrying

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitoring_active": monitoring_active
    }

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/trigger-check")
async def trigger_manual_check():
    """Manually trigger a data shift check"""
    global last_check_result
    
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")
    
    try:
        result = await monitor.check_data_shift()
        last_check_result = result
        
        # Update all Prometheus metrics
        update_prometheus_metrics(result)
        
        monitoring_metrics['checks_total'].inc()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in manual check: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get current monitoring status"""
    return {
        "monitoring_active": monitoring_active,
        "last_check_result": last_check_result,
        "last_check_timestamp": datetime.fromtimestamp(
            monitoring_metrics['last_check_timestamp']._value.get()
        ).isoformat() if monitoring_metrics['last_check_timestamp']._value.get() > 0 else None,
        "total_checks": monitoring_metrics['checks_total']._value.get()
    }

@app.get("/baseline")
async def get_baseline():
    """Get current baseline data"""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")
    
    try:
        baseline = monitor.get_baseline()
        return {
            "status": "success",
            "baseline": baseline
        }
    except Exception as e:
        logger.error(f"Error getting baseline: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/baseline/update")
async def update_baseline(baseline_data: BaselineUpdate):
    """Update baseline data"""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")
    
    try:
        baseline = {
            "avg_text_length": baseline_data.avg_text_length,
            "text_length_std": baseline_data.text_length_std,
            "language_distribution": baseline_data.language_distribution,
            "avg_request_volume": baseline_data.avg_request_volume,
            "updated_at": datetime.now().isoformat()
        }
        
        monitor.update_baseline(baseline)
        
        return {
            "status": "success",
            "message": "Baseline updated successfully",
            "baseline": baseline
        }
    except Exception as e:
        logger.error(f"Error updating baseline: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
