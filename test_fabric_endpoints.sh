#!/usr/bin/env bash
# =============================================================================
# Fabric MCP Server — Complete Endpoint Test Suite
# =============================================================================
# Corrected based on live Swagger docs at fabric.perceptor.us/docs
# 
# Usage:
#   chmod +x test_fabric_complete.sh
#   ./test_fabric_complete.sh                          # defaults to localhost:8000
#   FABRIC_URL=https://fabric.perceptor.us ./test_fabric_complete.sh
# =============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
FABRIC_URL="${FABRIC_URL:-http://localhost:8000}"
# Remove trailing slash if present
FABRIC_URL="${FABRIC_URL%/}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

passed=0
failed=0

# ── Helper Functions ──────────────────────────────────────────────────────────

test_get() {
    local endpoint="$1"
    local description="$2"
    local expect_error="${3:-false}"

    printf "${CYAN}[TEST]${NC} GET %-30s %s\n" "$endpoint" "$description"

    local url="${FABRIC_URL}${endpoint}"
    local http_code
    local response

    response=$(curl -s -w "\n%{http_code}" -X GET "$url"         -H "Accept: application/json" 2>&1) || true

    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        printf "  ${GREEN}✓ PASS${NC} (HTTP %s)\n" "$http_code"
        ((passed++))
    elif [[ "$http_code" =~ ^404$ ]] && [[ "$expect_error" == "true" ]]; then
        printf "  ${YELLOW}⚠ EXPECTED 404${NC} (HTTP %s)\n" "$http_code"
        ((passed++))
    elif [[ "$http_code" =~ ^4[0-9][0-9]$ ]]; then
        printf "  ${YELLOW}⚠ CLIENT ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    elif [[ "$http_code" =~ ^5[0-9][0-9]$ ]]; then
        printf "  ${RED}✗ SERVER ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    else
        printf "  ${RED}✗ UNREACHABLE${NC} (code: %s)\n" "$http_code"
        ((failed++))
    fi

    # Pretty-print JSON body (truncated)
    if command -v jq &>/dev/null && [ -n "$body" ]; then
        echo "$body" | jq '.' 2>/dev/null | head -10 | sed 's/^/    /'
    else
        echo "$body" | head -5 | sed 's/^/    /'
    fi
    echo ""
}

test_post() {
    local endpoint="$1"
    local description="$2"
    local payload="${3:-}"
    local content_type="${4:-application/json}"

    printf "${CYAN}[TEST]${NC} POST %-29s %s\n" "$endpoint" "$description"

    local url="${FABRIC_URL}${endpoint}"
    local http_code
    local response

    if [ -n "$payload" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST "$url"             -H "Content-Type: $content_type"             -H "Accept: application/json"             -d "$payload" 2>&1) || true
    else
        response=$(curl -s -w "\n%{http_code}" -X POST "$url"             -H "Accept: application/json" 2>&1) || true
    fi

    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    # For POST, 200, 201, 202 are success. 422 is acceptable for validation errors
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        printf "  ${GREEN}✓ PASS${NC} (HTTP %s)\n" "$http_code"
        ((passed++))
    elif [[ "$http_code" =~ ^422$ ]]; then
        printf "  ${YELLOW}⚠ VALIDATION ERROR${NC} (HTTP %s) - Expected for invalid payload\n" "$http_code"
        ((passed++))
    elif [[ "$http_code" =~ ^4[0-9][0-9]$ ]]; then
        printf "  ${YELLOW}⚠ CLIENT ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    elif [[ "$http_code" =~ ^5[0-9][0-9]$ ]]; then
        printf "  ${RED}✗ SERVER ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    else
        printf "  ${RED}✗ UNREACHABLE${NC} (code: %s)\n" "$http_code"
        ((failed++))
    fi

    # Pretty-print JSON body (truncated)
    if command -v jq &>/dev/null && [ -n "$body" ]; then
        echo "$body" | jq '.' 2>/dev/null | head -10 | sed 's/^/    /'
    else
        echo "$body" | head -5 | sed 's/^/    /'
    fi
    echo ""
}

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
printf "║     Fabric MCP Server — Complete Endpoint Test Suite             ║\n"
printf "║     Target: %-50s ║\n" "$FABRIC_URL"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# SECTION 1: HEALTH CHECKS
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 1: Health Checks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_get "/health" "Root health check"
test_get "/mcp/health" "MCP server health check"

# =============================================================================
# SECTION 2: DOCUMENTATION & SCHEMA
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 2: Documentation & Schema ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_get "/mcp/docs" "Swagger UI documentation page"
test_get "/mcp/docs/json" "OpenAPI JSON schema"

# =============================================================================
# SECTION 3: AGENT REGISTRY
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 3: Agent Registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# List all agents
test_get "/mcp/list_agents" "List all registered agents"

# Register a test agent
test_post "/mcp/register_agent" "Register test agent (test-agent-001)" '{
    "agent_id": "test-agent-001",
    "display_name": "Test Agent",
    "version": "1.0.0",
    "capabilities": [
        {"name": "echo", "description": "Echo back messages"},
        {"name": "healthcheck", "description": "Report health status"}
    ],
    "endpoint": {
        "transport": "http",
        "uri": "http://localhost:9001/mcp"
    }
}'

# Get specific agent details (may 404 if agent not found, that's ok)
test_get "/mcp/agent/test-agent-001" "Get test-agent-001 details"

# Register Aether Agent
test_post "/mcp/register_agent" "Register Aether Agent" '{
    "agent_id": "aether-agent",
    "display_name": "Aether Agent",
    "version": "1.0.0",
    "capabilities": [
        {"name": "reason", "description": "Advanced reasoning"},
        {"name": "orchestrate", "description": "Coordinate workflows"},
        {"name": "code", "description": "Code generation"}
    ],
    "endpoint": {
        "transport": "http",
        "uri": "http://aetheros.local:8080/mcp"
    }
}'

# List agents again to verify
test_get "/mcp/list_agents" "Verify agents registered"

# =============================================================================
# SECTION 4: TOOLS
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 4: Tools ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_get "/mcp/list_tools" "List all available tools"

# =============================================================================
# SECTION 5: TOPICS / PUB-SUB
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 5: Topics / Pub-Sub ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_get "/mcp/list_topics" "List active Pub/Sub topics"

# =============================================================================
# SECTION 6: METRICS
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 6: Metrics ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_get "/mcp/metrics" "Prometheus-style metrics"

# =============================================================================
# SECTION 7: MCP CALLS (Core A2A Communication)
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 7: MCP Calls (Agent-to-Agent) ━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Test basic MCP call structure
test_post "/mcp/call" "MCP Call - fabric.agent.list" '{
    "name": "fabric.agent.list",
    "arguments": {}
}'

# Test agent describe
test_post "/mcp/call" "MCP Call - fabric.agent.describe" '{
    "name": "fabric.agent.describe",
    "arguments": {
        "agent_id": "aether-agent"
    }
}'

# Test tool list
test_post "/mcp/call" "MCP Call - fabric.tool.list" '{
    "name": "fabric.tool.list",
    "arguments": {}
}'

# Test fabric.call (delegate to agent)
test_post "/mcp/call" "MCP Call - fabric.call (delegate)" '{
    "name": "fabric.call",
    "arguments": {
        "agent_id": "aether-agent",
        "capability": "reason",
        "task": "Analyze system health",
        "context": {"source": "test-suite"},
        "stream": false,
        "timeout_ms": 30000
    }
}'

# Test fabric.tool.call
test_post "/mcp/call" "MCP Call - fabric.tool.call" '{
    "name": "fabric.tool.call",
    "arguments": {
        "tool_id": "math.calculate",
        "capability": "calculate",
        "parameters": {
            "expression": "2 + 2 * 10"
        }
    }
}'

# Test message send
test_post "/mcp/call" "MCP Call - fabric.message.send" '{
    "name": "fabric.message.send",
    "arguments": {
        "from_agent": "test-agent-001",
        "to_agent": "aether-agent",
        "message_type": "task",
        "payload": {
            "task_type": "echo",
            "content": "Hello from test suite!"
        }
    }
}'

# Test message receive
test_post "/mcp/call" "MCP Call - fabric.message.receive" '{
    "name": "fabric.message.receive",
    "arguments": {
        "agent_id": "aether-agent",
        "count": 5,
        "block_ms": 1000
    }
}'

# =============================================================================
# SECTION 8: ERROR HANDLING TESTS
# =============================================================================
echo ""
echo "${BLUE}━━━ SECTION 8: Error Handling Tests ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Test 404 on non-existent agent
test_get "/mcp/agent/non-existent-agent-12345" "Get non-existent agent (expect 404)" "true"

# Test invalid MCP call
test_post "/mcp/call" "MCP Call - invalid method" '{
    "name": "invalid.method.name",
    "arguments": {}
}'

# Test malformed JSON
test_post "/mcp/call" "MCP Call - malformed JSON" '{invalid json here}'

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                        TEST SUMMARY                              ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
printf "║  ${GREEN}✓ Passed:  %-3d${NC}                                                  ║\n" "$passed"
printf "║  ${RED}✗ Failed:  %-3d${NC}                                                  ║\n" "$failed"
echo "║                                                                  ║"
printf "║  Total Tests: %-3d                                                ║\n" "$((passed + failed))"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Exit with appropriate code
if [ "$failed" -eq 0 ]; then
    printf "${GREEN}All tests passed!${NC}\n\n"
    exit 0
else
    printf "${RED}Some tests failed.${NC}\n\n"
    exit 1
fi
