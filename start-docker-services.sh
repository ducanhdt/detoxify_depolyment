#!/bin/bash

# Docker Compose startup script for vLLM and FastAPI services

set -e

echo "🚀 Starting vLLM and FastAPI services..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your actual GCP_PROJECT_ID"
    echo "   Then run this script again."
    exit 1
fi

# Check if credentials.json exists
if [ ! -f credentials.json ]; then
    echo "❌ credentials.json not found!"
    echo "   Please add your Google Cloud service account credentials file."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "   Please start Docker and try again."
    exit 1
fi

# Check if NVIDIA Docker runtime is available
if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi > /dev/null 2>&1; then
    echo "⚠️  NVIDIA Docker runtime not available!"
    echo "   GPU acceleration will not work."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start services
echo "🔧 Building and starting services..."
docker compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check vLLM
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ vLLM service is healthy"
else
    echo "❌ vLLM service is not responding"
fi

# Check FastAPI
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ FastAPI service is healthy"
else
    echo "❌ FastAPI service is not responding"
fi

echo ""
echo "🎉 Services are starting up!"
echo ""
echo "📊 Service URLs:"
echo "   vLLM Server:    http://localhost:8000"
echo "   FastAPI Service: http://localhost:8080"
echo ""
echo "📝 View logs:"
echo "   docker compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker compose down"
echo ""
echo "💡 Test the detoxification service:"
echo "   curl -X POST http://localhost:8080/detoxify \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"text\": \"Hello world\", \"language_id\": \"en\"}'"
