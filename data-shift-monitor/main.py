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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
data_shift_text_length_mean_change = Gauge(
    'data_shift_text_length_mean_change',
    'Percentage change in average text length compared to baseline'
)

data_shift_language_distribution_change = Gauge(
    'data_shift_language_distribution_change',
    'Percentage change in language distribution compared to baseline'
)

data_shift_request_volume_change = Gauge(
    'data_shift_request_volume_change',
    'Percentage change in request volume compared to baseline'
)

data_shift_last_check_timestamp = Gauge(
    'data_shift_last_check_timestamp',
    'Timestamp of last data shift check'
)

monitoring_checks_total = Counter(
    'monitoring_checks_total',
    'Total number of monitoring checks performed'
)

# Global variables
monitor: Optional[DataShiftMonitor] = None
monitoring_active = False
last_check_result: Optional[Dict[str, Any]] = None

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
                
                # Update Prometheus metrics
                data_shift_text_length_mean_change.set(result.get('text_length_change', 0))
                data_shift_language_distribution_change.set(result.get('language_distribution_change', 0))
                data_shift_request_volume_change.set(result.get('request_volume_change', 0))
                data_shift_last_check_timestamp.set(datetime.now().timestamp())
                
                monitoring_checks_total.inc()
                
                logger.info(f"Data shift check completed: {result}")
            
            # Wait 1 minute before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in background monitoring: {e}")
            await asyncio.sleep(60)  # Wait before retrying

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
        
        # Update Prometheus metrics
        data_shift_text_length_mean_change.set(result.get('text_length_change', 0))
        data_shift_language_distribution_change.set(result.get('language_distribution_change', 0))
        data_shift_request_volume_change.set(result.get('request_volume_change', 0))
        data_shift_last_check_timestamp.set(datetime.now().timestamp())
        
        monitoring_checks_total.inc()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in manual check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get current monitoring status"""
    return {
        "monitoring_active": monitoring_active,
        "last_check_result": last_check_result,
        "last_check_timestamp": datetime.fromtimestamp(
            data_shift_last_check_timestamp._value.get()
        ).isoformat() if data_shift_last_check_timestamp._value.get() > 0 else None,
        "total_checks": monitoring_checks_total._value.get()
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
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
