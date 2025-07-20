# Data Shift Monitoring Service

A FastAPI-based service that monitors data shift in text characteristics by querying Google Cloud Logging every 1 minute, calculating drift metrics, and exposing them to Prometheus for visualization in Grafana.

## Features

- **Real-time Monitoring**: Checks for data shift every 1 minute
- **Text Length Analysis**: Monitors changes in average text length compared to baseline
- **Language Distribution**: Tracks changes in language distribution patterns
- **Request Volume**: Monitors changes in request volume patterns
- **Prometheus Integration**: Exposes metrics for Prometheus scraping
- **Grafana Dashboard**: Pre-built dashboard for visualization
- **REST API**: Control endpoints for manual triggers and status checks

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   GCP Cloud Logging │    │  Data Shift Monitor │    │     Prometheus      │
│                     │────▶│                     │────▶│                     │
│   (Query logs)      │    │  (Calculate drift)  │    │  (Scrape metrics)   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                                                                    │
                                                                    ▼
                                                       ┌─────────────────────┐
                                                       │      Grafana        │
                                                       │                     │
                                                       │  (Visualize drift)  │
                                                       └─────────────────────┘
```

## Setup

### Prerequisites

- Docker and Docker Compose
- Google Cloud Platform credentials (credentials.json)
- Existing GCP project with Cloud Logging enabled

### Installation

1. **Update baseline configuration**:
   Edit `baseline.json` with your actual historical data:
   ```json
   {
     "avg_text_length": 150.0,
     "text_length_std": 75.0,
     "language_distribution": {
       "en": 70.0,
       "es": 15.0,
       "fr": 10.0,
       "de": 5.0
     },
     "avg_request_volume": 25.0,
     "created_at": "2025-01-16T19:46:30.000000",
     "description": "Production baseline from Jan 1-15, 2025"
   }
   ```

2. **Start the service**:
   ```bash
   docker-compose up -d data-shift-monitor
   ```

3. **Verify the service**:
   ```bash
   curl http://localhost:8081/health
   ```

## API Endpoints

### Health Check
```bash
GET /health
```
Returns service health status.

### Prometheus Metrics
```bash
GET /metrics
```
Returns Prometheus-formatted metrics.

### Manual Trigger
```bash
POST /trigger-check
```
Manually trigger a data shift analysis.

### Status Check
```bash
GET /status
```
Get current monitoring status and last results.

### Baseline Management
```bash
GET /baseline
```
Get current baseline data.

```bash
POST /baseline/update
Content-Type: application/json

{
  "avg_text_length": 150.0,
  "text_length_std": 75.0,
  "language_distribution": {
    "en": 70.0,
    "es": 15.0,
    "fr": 10.0
  },
  "avg_request_volume": 25.0
}
```
Update baseline data.

## Metrics

The service exposes the following Prometheus metrics:

- `data_shift_text_length_mean_change`: Percentage change in average text length
- `data_shift_language_distribution_change`: Percentage change in language distribution
- `data_shift_request_volume_change`: Percentage change in request volume
- `data_shift_last_check_timestamp`: Timestamp of last check
- `monitoring_checks_total`: Total number of monitoring checks performed

## Grafana Dashboard

The service includes a pre-built Grafana dashboard (`data_shift_monitoring.json`) with:

- **Text Length Change**: Time series showing percentage changes
- **Language Distribution Change**: Tracking language pattern shifts
- **Request Volume Change**: Monitoring traffic pattern changes
- **Monitoring Checks**: Total checks performed

Access the dashboard at: `http://localhost:5000` (admin/admin)

## Configuration

### Environment Variables

- `GCP_PROJECT_ID`: Your GCP project ID (default: meta-triode-457409-a9)

### Files

- `baseline.json`: Historical baseline data for comparison
- `main.py`: FastAPI application with endpoints
- `monitoring.py`: Core monitoring logic
- `gcp_client.py`: Google Cloud Logging client
- `metrics_calculator.py`: Data shift calculation logic

## Monitoring Strategy

1. **Baseline Establishment**: Set baseline from historical data
2. **Continuous Monitoring**: Check every 1 minute for changes
3. **Drift Detection**: Calculate percentage changes vs baseline
4. **Alerting**: Set thresholds in Grafana for alerts
5. **Investigation**: Use API endpoints to investigate anomalies

## Troubleshooting

### Common Issues

1. **No data in logs**:
   - Check GCP credentials
   - Verify log name matches your service
   - Ensure logs contain required fields

2. **High drift values**:
   - Verify baseline data is representative
   - Check for recent changes in your application
   - Review time period for analysis

3. **Service not starting**:
   - Check Docker logs: `docker logs data-shift-monitor-service`
   - Verify credentials.json is mounted correctly
   - Check port 8081 is available

### Debug Commands

```bash
# Check service logs
docker logs data-shift-monitor-service

# Test GCP connection
curl http://localhost:8081/status

# Manual trigger
curl -X POST http://localhost:8081/trigger-check

# Check metrics
curl http://localhost:8081/metrics
```

## Customization

### Adding New Metrics

1. Add metric calculation in `metrics_calculator.py`
2. Add Prometheus gauge in `main.py`
3. Update dashboard JSON for visualization

### Changing Check Frequency

Modify the sleep time in `background_monitoring()` function in `main.py`:
```python
await asyncio.sleep(60)  # Change from 60 seconds to desired interval
```

### Custom Baseline Logic

Override the `_load_baseline()` method in `monitoring.py` to implement custom baseline loading logic.
