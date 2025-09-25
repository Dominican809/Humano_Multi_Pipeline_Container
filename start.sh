#!/bin/bash
# Humano Multi-Pipeline Container Startup Script

set -e

echo "🚀 Starting Humano Multi-Pipeline Container..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "📋 Copying example configuration..."
    cp config.env.example .env
    echo "✅ Please edit .env with your actual values before running again"
    echo "   nano .env"
    exit 1
fi

# Check if required directories exist
echo "📁 Checking directory structure..."
required_dirs=(
    "shared/database/state"
    "shared/logs"
    "viajeros_pipeline/Exceles"
    "si_pipeline/Comparador_Humano/exceles"
    "viajeros_pipeline/data"
    "si_pipeline/data"
)

for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "📁 Creating directory: $dir"
        mkdir -p "$dir"
    fi
done

# Check if SI old file exists
if [ ! -f "si_pipeline/Comparador_Humano/exceles/Asegurados_SI_old.xlsx" ]; then
    echo "⚠️  SI old file not found!"
    echo "📋 You need to place Asegurados_SI_old.xlsx in si_pipeline/Comparador_Humano/exceles/"
    echo "   This file is required for SI pipeline comparison"
    exit 1
fi

echo "✅ Directory structure verified"

# Build and start container
echo "🔨 Building Docker container..."
docker compose up -d --build

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 10

# Check container status
echo "📊 Container status:"
docker compose ps

# Show logs
echo "📋 Recent logs:"
docker compose logs --tail=20 humano-multi-pipeline

echo ""
echo "🎉 Humano Multi-Pipeline Container is running!"
echo ""
echo "📊 Monitor with:"
echo "   docker compose logs -f humano-multi-pipeline"
echo ""
echo "🔍 Check health with:"
echo "   docker compose ps"
echo "   docker exec humano-multi-pipeline python /app/email_watcher/health_check.py"
echo ""
echo "🔄 Enable continuous monitoring with:"
echo "   docker exec -it humano-multi-pipeline python /app/email_watcher/health_check.py --monitor"
echo ""
echo "🛑 Stop with:"
echo "   docker compose down"
