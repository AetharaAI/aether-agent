#!/bin/bash

# Aether Complete System Startup Script
# This script starts all components of the Aether system

set -e

echo "================================================"
echo "  Starting Aether Complete System"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Redis is running
echo -e "${YELLOW}[1/4] Checking Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}✗ Redis is not running${NC}"
    echo "Please start Redis with: redis-server"
    exit 1
fi
echo -e "${GREEN}✓ Redis is running${NC}"
echo ""

# Check Python dependencies
echo -e "${YELLOW}[2/4] Checking Python dependencies...${NC}"
if ! python3 -c "import fastapi, uvicorn, redis, aiohttp" > /dev/null 2>&1; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip3 install -r requirements.txt
fi
echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# Start Aether API Server
echo -e "${YELLOW}[3/4] Starting Aether API Server...${NC}"
cd "$(dirname "$0")"

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start API server in background
python3 -m aether.api_server > logs/api_server.log 2>&1 &
API_PID=$!
echo $API_PID > .api_server.pid

# Wait for API server to be ready
echo "Waiting for API server to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API Server started (PID: $API_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ API Server failed to start${NC}"
        echo "Check logs/api_server.log for details"
        exit 1
    fi
    sleep 1
done
echo ""

# Start UI (if in development mode)
echo -e "${YELLOW}[4/4] Starting Aether UI...${NC}"
if [ -d "../aether-ui" ]; then
    cd ../aether-ui
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing UI dependencies..."
        pnpm install
    fi
    
    # Start dev server in background
    pnpm dev > ../aether_project/logs/ui_dev.log 2>&1 &
    UI_PID=$!
    echo $UI_PID > ../aether_project/.ui_dev.pid
    
    echo -e "${GREEN}✓ UI Dev Server started (PID: $UI_PID)${NC}"
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Aether System Started Successfully!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo "API Server:  http://localhost:8000"
    echo "UI:          http://localhost:3000"
    echo "Health:      http://localhost:8000/health"
    echo ""
    echo "Logs:"
    echo "  API:       logs/api_server.log"
    echo "  UI:        logs/ui_dev.log"
    echo ""
    echo "To stop: ./stop_aether.sh"
    echo ""
else
    echo -e "${YELLOW}UI directory not found. Only API server started.${NC}"
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Aether API Server Started!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo "API Server:  http://localhost:8000"
    echo "Health:      http://localhost:8000/health"
    echo ""
    echo "To stop: ./stop_aether.sh"
    echo ""
fi
