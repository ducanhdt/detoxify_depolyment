# Docker Compose Setup for vLLM and FastAPI Service

This Docker Compose configuration runs both the vLLM server and the FastAPI detoxification service.

## Prerequisites

1. **Docker and Docker Compose** installed
2. **NVIDIA Docker runtime** for GPU support
3. **Google Cloud credentials** (`credentials.json`) in the root directory
4. **Environment variables** configured

## Setup Instructions

### 1. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` and set your Google Cloud Project ID:

```bash
GCP_PROJECT_ID=your-actual-gcp-project-id
```

### 2. Google Cloud Credentials

Make sure you have `credentials.json` in the root directory with appropriate permissions for:
- Google Cloud Logging
- Google Cloud Storage (if using log archival)

### 3. NVIDIA Docker Runtime

Ensure NVIDIA Docker runtime is installed and configured:

```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## Usage

### Start the services

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f fastapi-service
docker compose logs -f vllm
```

### Stop the services

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Rebuild services

```bash
# Rebuild FastAPI service after code changes
docker compose build fastapi-service
docker compose up -d fastapi-service
```

## Service Endpoints

- **vLLM Server**: http://localhost:8000
  - Health check: http://localhost:8000/health
  - Metrics: http://localhost:8000/metrics
  - OpenAI API: http://localhost:8000/v1/chat/completions

- **FastAPI Service**: http://localhost:8080
  - Health check: http://localhost:8080/health
  - Detoxification endpoint: http://localhost:8080/detoxify

## Testing the Services

### Test vLLM directly

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/gemma-3-12b-it-bnb-4bit",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### Test FastAPI detoxification service

```bash
curl -X POST http://localhost:8080/detoxify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test message",
    "language_id": "en"
  }'
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │      vLLM       │
│   Service       │───▶│     Server      │
│   (Port 8080)   │    │   (Port 8000)   │
└─────────────────┘    └─────────────────┘
         │                       │
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  Google Cloud   │    │  HuggingFace    │
│    Logging      │    │     Cache       │
└─────────────────┘    └─────────────────┘
```

## Troubleshooting

### Common Issues

1. **GPU not accessible**: Ensure NVIDIA Docker runtime is installed
2. **Model loading fails**: Check HuggingFace cache and network connectivity
3. **Permission errors**: Ensure credentials.json has correct permissions
4. **Port conflicts**: Check if ports 8000 and 8080 are available

### Logs and Debugging

```bash
# Check service health
docker compose ps

# View detailed logs
docker compose logs --tail=100 -f

# Execute commands in running container
docker compose exec fastapi-service bash
docker compose exec vllm bash
```

### Resource Requirements

- **GPU**: NVIDIA GPU with at least 8GB VRAM
- **Memory**: At least 16GB RAM recommended
- **Storage**: At least 20GB for model cache
