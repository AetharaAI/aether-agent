#!/bin/bash

# Aether Complete System Stop Script

set -e

echo "================================================"
echo "  Stopping Aether System"
echo "================================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "$0")"

# Stop API Server
if [ -f .api_server.pid ]; then
    API_PID=$(cat .api_server.pid)
    echo -e "${YELLOW}Stopping API Server (PID: $API_PID)...${NC}"
    if kill $API_PID 2>/dev/null; then
        echo -e "${GREEN}✓ API Server stopped${NC}"
    else
        echo -e "${YELLOW}API Server process not found${NC}"
    fi
    rm .api_server.pid
else
    echo -e "${YELLOW}No API Server PID file found${NC}"
fi

# Stop UI Dev Server
if [ -f .ui_dev.pid ]; then
    UI_PID=$(cat .ui_dev.pid)
    echo -e "${YELLOW}Stopping UI Dev Server (PID: $UI_PID)...${NC}"
    if kill $UI_PID 2>/dev/null; then
        echo -e "${GREEN}✓ UI Dev Server stopped${NC}"
    else
        echo -e "${YELLOW}UI Dev Server process not found${NC}"
    fi
    rm .ui_dev.pid
else
    echo -e "${YELLOW}No UI Dev Server PID file found${NC}"
fi

echo ""
echo -e "${GREEN}Aether System Stopped${NC}"
